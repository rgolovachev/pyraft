import subprocess
import time
import requests
import random

def start_process(id):
    return subprocess.Popen(['python3', 'raft.py', str(id), "availability_test_cfg.conf"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    nodes = [(start_process(0), 0), (start_process(1), 1), (start_process(2), 2), (start_process(3), 3), (start_process(4), 4)]

    nodesCfg = None
    with open('availability_test_cfg.conf', 'r') as f:
        line_parts = map(lambda line: line.split(), f.read().strip().split("\n"))
        nodesCfg = dict([(int(p[0]), (p[1], int(p[2]), None)) for p in line_parts])

    def finish_test(is_succ):
        for node in nodes:
            node[0].terminate()
        if not is_succ:
            exit(1)

    def failed_status_code(expected, actual):
        print(f"expected status_code is {expected}, found {actual}")
        finish_test(False)

    def failed_value(expected, actual):
        print(f"expected value is {expected}, found {actual}")
        finish_test(False)

    def check_get_from_replica(leader_address, key, value, replicas, suspend_idx):
        suspended_addr = set()
        for idx in suspend_idx:
            (host, port, _) = nodesCfg[replicas[idx][1]]
            suspended_addr.add(f"{host}:{port-1000}")

        replica_address = None
        last_applied = 0
        while replica_address == None or replica_address in suspended_addr:
            get_resp = requests.get(f"http://{leader_address}/get?key={key}", allow_redirects=False)
            if get_resp.status_code != 302:
                failed_status_code(302, get_resp.status_code)
            replica_address = get_resp.headers['Location']
            last_applied = get_resp.json()['last_applied']

        get_resp = requests.get(f"http://{replica_address}/get?key={key}&last_applied={last_applied}")
        while get_resp.status_code == 429:
            get_resp = requests.get(f"http://{replica_address}/get?key={key}&last_applied={last_applied}")
        if get_resp.status_code != 200:
            print('failed addr: ' + replica_address)
            failed_status_code(200, get_resp.status_code)
        if get_resp.json()[key] != value:
            failed_value(value, get_resp.json()[key])

    def get_leader(node_addr):
        leader_resp = requests.get(f'http://{node_addr}/leader')
        if leader_resp.status_code != 200:
            print(f"failed to get leader, response: {leader_resp.text}")
            finish_test(False)
        return leader_resp.json()['leader_id'], leader_resp.json()['address']

    def suspend_nodes(replicas, suspend_idx, period, leader_address=None):
        for idx in suspend_idx:
            replica = replicas[idx]
            (host, port, _) = nodesCfg[replica[1]]
            addr = f"{host}:{port-1000}"
            print('suspend (replica): ' + addr)
            suspend_resp = requests.post(f'http://{addr}/suspend?period={period}')
            if suspend_resp.status_code != 200:
                print(f"failed to suspend replica {replica[1]}")
                finish_test(False)
        if leader_address != None:
            print('suspend (LEADER): ' + leader_address)
            suspend_resp = requests.post(f'http://{leader_address}/suspend?period={period}')
            if suspend_resp.status_code != 200:
                print(f"failed to suspend replica {replica[1]}")
                finish_test(False)


    time.sleep(0.8)

    #
    # start of the test
    #
    try:
        (host, port, _) = nodesCfg[0]
        leader_id, leader_address = get_leader(f"{host}:{port-1000}")
        print('LEADER is ' + leader_address)
        replicas = []
        start_leader = None
        for (node, id) in nodes:
            if id != int(leader_id):
                replicas.append((node, id))
            else:
                start_leader = (node, id)
        random.shuffle(replicas)
        suspend_idx = [0, 1]

        #
        # create key and suspend two replicas
        #
        key = 'test_key'
        value = 'test_value'

        create_resp = requests.post(f"http://{leader_address}/create?key={key}&value={value}", allow_redirects=False)
        if create_resp.status_code != 200:
            failed_status_code(200, create_resp.status_code)
        suspend_nodes(replicas, suspend_idx, 5)
        for i in range(100):
            check_get_from_replica(leader_address, key, value, replicas, suspend_idx)

        # wait until nodes wake up
        time.sleep(5)

        suspend_idx = []
        for i in range(100):
            check_get_from_replica(leader_address, key, value, replicas, suspend_idx)

        #
        # create key and suspend leader + one replica
        #
        key2 = 'test_key2'
        value2 = 'test_value2'

        random.shuffle(replicas)
        suspend_idx = [0]

        create_resp = requests.post(f"http://{leader_address}/create?key={key2}&value={value2}", allow_redirects=False)
        if create_resp.status_code != 200:
            failed_status_code(200, create_resp.status_code)
        suspend_nodes(replicas, suspend_idx, 5, leader_address)
        (host, port, _) = nodesCfg[replicas[1][1]]
        time.sleep(0.3)
        leader_id, leader_address = get_leader(f"{host}:{port-1000}")
        print('new leader_id and leader_address: ' + str(leader_id) + ', ' + str(leader_address))
        replicas.append(start_leader)
        suspend_idx.append(len(replicas) - 1)
        for i in range(100):
            check_get_from_replica(leader_address, key, value, replicas, suspend_idx)
            check_get_from_replica(leader_address, key2, value2, replicas, suspend_idx)

        # wait until nodes wake up
        time.sleep(5)

        suspend_idx = []
        for i in range(100):
            check_get_from_replica(leader_address, key, value, replicas, suspend_idx)
            check_get_from_replica(leader_address, key2, value2, replicas, suspend_idx)
        
        print("availability test passed")
    except Exception as e:
        print(f"caught exception: {e}")
        finish_test(False)

    finish_test(True)

if __name__ == "__main__":
    main()
