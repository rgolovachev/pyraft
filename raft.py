import sys
import random
import concurrent.futures
import threading
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify

import grpc
from grpc_reflection.v1alpha import reflection

import raft_pb2_grpc as pb2_grpc
import raft_pb2 as pb2


[HEARTBEAT_DURATION, ELECTION_DURATION_FROM, ELECTION_DURATION_TO] = [x for x in [50, 150, 300]]

#
# global state
#
is_terminating = False
is_suspended = False
state_lock = threading.Lock()
election_timer_fired = threading.Event()
heartbeat_events = {}
state = {
    'election_campaign_timer': None,
    'election_timeout': -1,
    'type': 'follower',
    'nodes': None,
    'term': 0,
    'vote_count': 0,
    'voted_for_id': -1,
    'leader_id': -1,
    'commit_idx': -1,
    'last_applied': -1,
    'logs': [],
    'next_idx': [],
    'match_idx': [],
    'replicate_vote_count': 0,
    'hash_table': {}
}

#
# election timer functions
#
def select_election_timeout():
    return random.randrange(ELECTION_DURATION_FROM, ELECTION_DURATION_TO) * 0.001

def reset_election_campaign_timer():
    stop_election_campaign_timer()
    state['election_campaign_timer'] = threading.Timer(state['election_timeout'], election_timer_fired.set)
    state['election_campaign_timer'].start()


def select_new_election_timeout_duration():
    state['election_timeout'] = select_election_timeout()


def stop_election_campaign_timer():
    if state['election_campaign_timer']:
        state['election_campaign_timer'].cancel()


#
# elections
#
def start_election():
    with state_lock:
        state['type'] = 'candidate'
        state['leader_id'] = -1
        state['term'] += 1
        # vote for ourselves
        state['vote_count'] = 1
        state['voted_for_id'] = state['id']

    print(f"I am a candidate. Term: {state['term']}")
    for id in state['nodes'].keys():
        if id != state['id']:
            t = threading.Thread(target=request_vote_worker_thread, args=(id,))
            t.start()
    # now RequestVote threads have started,
    # lets set a timer for the end of the election
    reset_election_campaign_timer()


def has_enough_votes():
    required_votes = (len(state['nodes']) // 2) + 1
    return state['vote_count'] >= required_votes


def has_enough_replicate_votes():
    required_votes = (len(state['nodes']) // 2) + 1
    return state['replicate_vote_count'] >= required_votes


def finalize_election():
    stop_election_campaign_timer()
    with state_lock:
        if state['type'] != 'candidate':
            return

        if has_enough_votes():
            # become a leader
            state['type'] = 'leader'
            state['leader_id'] = state['id']
            state['vote_count'] = 0
            state['voted_for_id'] = -1

            for i in range(0, len(state['nodes'])):
                if i == state['id']:
                    continue

                state['next_idx'][i] = 0
                state['match_idx'][i] = -1

            start_heartbeats()
            print("Votes received")
            print(f"I am a leader. Term: {state['term']}")
            return
        # if election was unsuccessful
        # then pick new timeout duration
        become_a_follower()
        select_new_election_timeout_duration()
        reset_election_campaign_timer()


def become_a_follower():
    if state['type'] != 'follower':
        print(f"I am a follower. Term: {state['term']}")
    state['type'] = 'follower'
    state['voted_for_id'] = -1
    state['vote_count'] = 0

#
# heartbeats
#
def start_heartbeats():
    for id in heartbeat_events:
        heartbeat_events[id].set()


#
# thread functions
#
def request_vote_worker_thread(id_to_request):
    ensure_connected(id_to_request)
    (_, _, stub) = state['nodes'][id_to_request]
    try:
        resp = stub.RequestVote(pb2.VoteRequest(
            term=state['term'],
            candidate_id=state['id'],
            last_log_index=len(state['logs']) - 1,
            last_log_term=state['logs'][-1][0] if len(state['logs']) > 0 else -1
        ), timeout=0.1)

        with state_lock:
            # if requested node replied for too long,
            # and during this time candidate stopped
            # being a candidate, then do nothing
            if state['type'] != 'candidate' or is_suspended:
                return

            if state['term'] < resp.term:
                state['term'] = resp.term
                become_a_follower()
                reset_election_campaign_timer()
            elif resp.result:
                state['vote_count'] += 1

        # got enough votes, no need to wait for the end of the timeout
        if has_enough_votes():
            finalize_election()
    except grpc.RpcError:
        reopen_connection(id_to_request)


def election_timeout_thread():
    while not is_terminating:
        if election_timer_fired.wait(timeout=0.5):
            election_timer_fired.clear()
            if is_suspended:
                continue

            # election timer just fired
            if state['type'] == 'follower':
                # node didn't receive any heartbeats on time
                # that's why it should become a candidate
                print("The leader is dead")
                start_election()
            elif state['type'] == 'candidate':
                # okay, election is over
                # we need to count votes
                finalize_election()
            # if somehow we got here while being a leader,
            # then do nothing


def heartbeat_thread(id_to_request):
    while not is_terminating:
        try:
            if heartbeat_events[id_to_request].wait(timeout=0.5):
                heartbeat_events[id_to_request].clear()

                if (state['type'] != 'leader') or is_suspended:
                    continue

                ensure_connected(id_to_request)
                (_, _, stub) = state['nodes'][id_to_request]

                # In case this is heartbeat send -404 as value in replicate logs params
                resp = stub.AppendEntries(pb2.AppendRequest(
                    term=state['term'],
                    leader_id=state['id'],
                    prev_log_index=-404,
                    prev_log_term=-404,
                    entries=None,
                    leader_commit=-404
                ), timeout=0.100)

                if (state['type'] != 'leader') or is_suspended:
                    continue

                with state_lock:
                    if state['term'] < resp.term:
                        reset_election_campaign_timer()
                        state['term'] = resp.term
                        become_a_follower()
                threading.Timer(HEARTBEAT_DURATION * 0.001, heartbeat_events[id_to_request].set).start()
        except grpc.RpcError:
            reopen_connection(id_to_request)


def replicate_logs_thread(id_to_request):
    if (state['type'] != 'leader') or is_suspended:
        return

    entries = []
    idx_from = state['next_idx'][id_to_request]
    for (term, (_, key, value)) in state['logs'][idx_from:]:
        entries.append(pb2.Entry(term=term, key=key, value=value))

    try:
        ensure_connected(id_to_request)

        (_, _, stub) = state['nodes'][id_to_request]
        resp = stub.AppendEntries(pb2.AppendRequest(
            term=state['term'],
            leader_id=state['id'],
            prev_log_index=state['next_idx'][id_to_request] - 1,
            prev_log_term=state['logs'][state['next_idx'][id_to_request] - 1][0] if state['next_idx'][id_to_request] > 0 else -1,
            entries=entries,
            leader_commit=state['commit_idx']
        ), timeout=0.100)

        with state_lock:
            if resp.result:
                state['next_idx'][id_to_request] = len(state['logs'])
                state['match_idx'][id_to_request] = len(state['logs']) - 1
            else:
                state['next_idx'][id_to_request] = max(state['next_idx'][id_to_request] - 1, 0)
                state['match_idx'][id_to_request] = min(state['match_idx'][id_to_request],
                                                        state['next_idx'][id_to_request] - 1)

    except grpc.RpcError:
        state['next_idx'][id_to_request] = 0
        state['match_idx'][id_to_request] = -1
        reopen_connection(id_to_request)


#
# Logs replication
#
def replicate_logs():
    while not is_terminating:
        time.sleep(0.5)

        if (state['type'] != 'leader') or is_suspended or len(state['logs']) == 0:
            continue

        with state_lock:
            curr_id = state['id']
            state['match_idx'][state['id']] = len(state['logs']) - 1

        threads = []
        for node_id in nodes:
            if curr_id == node_id:
                continue

            t = threading.Thread(target=replicate_logs_thread, args=(node_id,))
            t.start()
            threads.append(t)

        for thread in threads:
            thread.join()

        with state_lock:
            state['replicate_vote_count'] = 0
            for i in range(0, len(state['match_idx'])):
                if state['match_idx'][i] > state['commit_idx']:
                    state['replicate_vote_count'] += 1

            if has_enough_replicate_votes():
                state['commit_idx'] += 1

            while state['commit_idx'] > state['last_applied']:
                state['last_applied'] += 1
                _, key, value = state['logs'][state['last_applied']][1]
                state['hash_table'][key] = value


#
# gRPC server handler
#
def wake_up_after_suspend():
    global is_suspended
    is_suspended = False
    if state['type'] == 'leader':
        start_heartbeats()
    else:
        reset_election_campaign_timer()


class Handler(pb2_grpc.RaftNodeServicer):
    def RequestVote(self, request, context):
        global is_suspended
        if is_suspended:
            return

        reset_election_campaign_timer()
        with state_lock:
            if state['term'] < request.term:
                state['term'] = request.term
                become_a_follower()

            failure_reply = pb2.ResultWithTerm(term=state['term'], result=False)
            if request.term < state['term']:
                return failure_reply
            elif request.last_log_index < len(state['logs']) - 1:
                return failure_reply
            elif len(state['logs']) != 0 and request.last_log_index == len(
                    state['logs']) - 1 and request.last_log_term != state['logs'][-1][0]:
                return failure_reply
            elif state['term'] == request.term and state['voted_for_id'] == -1:
                become_a_follower()
                state['voted_for_id'] = request.candidate_id
                print(f"Voted for node {state['voted_for_id']}")
                return pb2.ResultWithTerm(term=state['term'], result=True)

            return failure_reply

    def AppendEntries(self, request, context):
        global is_suspended
        if is_suspended:
            return

        reset_election_campaign_timer()

        with state_lock:
            is_heartbeat = (
                    request.prev_log_index == -404 or
                    request.prev_log_term == -404 or
                    request.leader_commit == -404
            )

            if request.term > state['term']:
                state['term'] = request.term
                become_a_follower()
            if is_heartbeat and request.term == state['term']:
                state['leader_id'] = request.leader_id
                return pb2.ResultWithTerm(term=state['term'], result=True)

            failure_reply = pb2.ResultWithTerm(term=state['term'], result=False)
            if request.term < state['term']:
                return failure_reply
            elif request.prev_log_index > len(state['logs']) - 1:
                return failure_reply
            elif request.term == state['term']:
                state['leader_id'] = request.leader_id

                success_reply = pb2.ResultWithTerm(term=state['term'], result=True)

                entries = []
                for entry in request.entries:
                    entries.append((entry.term, ('set', entry.key, entry.value)))

                start_idx = request.prev_log_index + 1

                logs_start = state['logs'][:start_idx]
                logs_middle = state['logs'][start_idx: start_idx + len(entries)]
                logs_end = state['logs'][start_idx + len(entries):]

                has_conflicts = False
                for i in range(0, len(logs_middle)):
                    if logs_middle[i][0] != entries[i][0]:
                        has_conflicts = True
                        break

                if has_conflicts:
                    state['logs'] = logs_start + entries
                else:
                    state['logs'] = logs_start + entries + logs_end

                if request.leader_commit > state['commit_idx']:
                    state['commit_idx'] = min(request.leader_commit, len(state['logs']) - 1)

                    while state['commit_idx'] > state['last_applied']:
                        state['last_applied'] += 1
                        _, key, value = state['logs'][state['last_applied']][1]
                        state['hash_table'][key] = value

                return success_reply

            return failure_reply

    def GetLeader(self, request, context):
        global is_suspended
        if is_suspended:
            return

        if state.get('leader_id') is None:
            return

        (host, port, _) = state['nodes'][state['leader_id']]
        return pb2.GetLeaderReply(leader_id=state['leader_id'], address=f"{host}:{port}")

    def Suspend(self, request, context):
        global is_suspended
        if is_suspended:
            return

        is_suspended = True
        threading.Timer(request.period, wake_up_after_suspend).start()
        return pb2.EmptyMessage()

    def GetVal(self, request, context):
        global is_suspended
        if is_suspended:
            return

        with state_lock:
            value = state['hash_table'].get(request.key)
            success = (value is not None)
            value = value if success else "None"

            return pb2.GetReply(success=success, value=value)

    def SetVal(self, request, context):
        global is_suspended
        if is_suspended:
            return

        if state['type'] != 'leader':
            if state['leader_id'] == -1:
                return pb2.SetReply(success=False)

            ensure_connected(state['leader_id'])

            (_, _, stub) = state['nodes'][state['leader_id']]
            try:
                resp = stub.SetVal(pb2.SetRequest(key=request.key, value=request.value), timeout=0.100)
            except:
                return pb2.SetReply(success=False)

            return resp

        with state_lock:
            state['logs'].append((state['term'], ('set', request.key, request.value)))
            return pb2.SetReply(success=True)

#
# other
#
def ensure_connected(id):
    if id == state['id']:
        raise "Shouldn't try to connect to itself"
    (host, port, stub) = state['nodes'][id]
    if not stub:
        channel = grpc.insecure_channel(f"{host}:{port}")
        stub = pb2_grpc.RaftNodeStub(channel)
        state['nodes'][id] = (host, port, stub)


def reopen_connection(id):
    if id == state['id']:
        raise "Shouldn't try to connect to itself"
    (host, port, stub) = state['nodes'][id]
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = pb2_grpc.RaftNodeStub(channel)
    state['nodes'][id] = (host, port, stub)


def start_server(state):
    (ip, port, _stub) = state['nodes'][state['id']]
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_RaftNodeServicer_to_server(Handler(), server)
    SERVICE_NAMES = (pb2.DESCRIPTOR.services_by_name['RaftNode'].full_name, reflection.SERVICE_NAME)
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    server.add_insecure_port(f"{ip}:{port}")
    server.start()
    return server

app = Flask(__name__)

#
# HTTP server handler
#
@app.route('/get', methods=['GET'])
def get_value():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'Key query param is required'}), 400
    channel = grpc.insecure_channel(state['node_addr'])
    stub = pb2_grpc.RaftNodeStub(channel)
    try:
        resp = stub.GetVal(pb2.GetRequest(key=key))
        if resp.success == False:
            return jsonify({'error': 'Key is not found'}), 404

        return jsonify({key: resp.value}), 200
    except:
        return jsonify({'error': 'Internal error'}), 500

@app.route('/create', methods=['POST'])
def create_value():
    key = request.args.get('key')
    value = request.args.get('value')
    if not key or not value:
        return jsonify({'error': 'Key and value query params are required'}), 400
    channel = grpc.insecure_channel(state['node_addr'])
    stub = pb2_grpc.RaftNodeStub(channel)
    try:
        resp = stub.GetVal(pb2.GetRequest(key=key))
        if resp.value != "None":
            return jsonify({'error': 'Key value pair already exists', key: value}), 400

        resp = stub.SetVal(pb2.SetRequest(key=key, value=value))
        if resp.success == False:
            return jsonify({'error': 'Internal error'}), 500

        return jsonify({'error': 'KV pair created successfuly'}), 200
    except:
        return jsonify({'error': 'Internal error'}), 500

@app.route('/update', methods=['PUT'])
def update_value():
    key = request.args.get('key')
    value = request.args.get('value')
    if not key or not value:
        return jsonify({'error': 'Key and value query params are required'}), 400
    channel = grpc.insecure_channel(state['node_addr'])
    stub = pb2_grpc.RaftNodeStub(channel)
    try:
        resp = stub.GetVal(pb2.GetRequest(key=key))
        if resp.value == "None":
           return jsonify({'error': 'Key is not found'}), 404

        resp = stub.SetVal(pb2.SetRequest(key=key, value=value))
        if resp.success == False:
            return jsonify({'error': 'Internal error'}), 500

        return jsonify({'error': 'KV pair updated successfuly'}), 200
    except:
        return jsonify({'error': 'Internal error'}), 500

@app.route('/delete', methods=['DELETE'])
def delete_value():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'Key query param is required'}), 400
    channel = grpc.insecure_channel(state['node_addr'])
    stub = pb2_grpc.RaftNodeStub(channel)
    try:
        resp = stub.GetVal(pb2.GetRequest(key=key))
        if resp.value == "None":
           return jsonify({'error': 'Key is not found'}), 404

        resp = stub.SetVal(pb2.SetRequest(key=key, value=None))
        if resp.success == False:
            return jsonify({'error': 'Internal error'}), 500

        return jsonify({'error': 'Value deleted successfuly'}), 200
    except:
        return jsonify({'error': 'Internal error'}), 500


def main(id, nodes):
    election_th = threading.Thread(target=election_timeout_thread)
    election_th.start()

    heartbeat_threads = []
    for node_id in nodes:
        if id != node_id:
            heartbeat_events[node_id] = threading.Event()
            t = threading.Thread(target=heartbeat_thread, args=(node_id,))
            t.start()
            heartbeat_threads.append(t)

    state['id'] = id
    state['nodes'] = nodes
    state['type'] = 'follower'
    state['term'] = 0
    state['next_idx'] = [0] * len(state['nodes'])
    state['match_idx'] = [-1] * len(state['nodes'])

    log_replication_th = threading.Thread(target=replicate_logs)
    log_replication_th.start()

    (host, port, _) = nodes[id]

    state['node_addr'] = f"{host}:{port}"
    http_server_th = threading.Thread(target=app.run, args=(host,port-1000,))
    http_server_th.daemon = True
    http_server_th.start()

    server = start_server(state)
    print(f"The server starts at {host}:{port}")
    print(f"I am a follower. Term: 0")
    select_new_election_timeout_duration()
    reset_election_campaign_timer()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        global is_terminating
        is_terminating = True
        server.stop(0)
        print("Shutting down")

        election_th.join()
        [t.join() for t in heartbeat_threads]


if __name__ == '__main__':
    [id] = sys.argv[1:]
    nodes = None
    with open("config.conf", 'r') as f:
        line_parts = map(lambda line: line.split(), f.read().strip().split("\n"))
        nodes = dict([(int(p[0]), (p[1], int(p[2]), None)) for p in line_parts])
        print(list(nodes))
    main(int(id), nodes)
