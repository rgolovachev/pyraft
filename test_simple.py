import subprocess
import time
import requests
import random

def start_process(id):
    return subprocess.Popen(['python3', 'raft.py', str(id)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    nodes = [start_process(0), start_process(1), start_process(2)]

    def finish_test(is_succ):
        for node in nodes:
            node.terminate()
        if not is_succ:
            exit(1)

    def failed_status_code(expected, actual):
        print(f"expected status_code is {expected}, found {actual}")
        finish_test(False)

    def failed_value(expected, actual):
        print(f"expected value is {expected}, found {actual}")
        finish_test(False)

    def check_get_from_replica(leader_address, key, value, after_delete=False):
        get_resp = requests.get(f"http://{leader_address}/get?key={key}", allow_redirects=False)
        if get_resp.status_code != 302:
            failed_status_code(302, get_resp.status_code)
        replica_address = get_resp.headers['Location']
        last_applied = get_resp.json()['last_applied']

        get_resp = requests.get(f"http://{replica_address}/get?key={key}&last_applied={last_applied}")
        while get_resp.status_code == 429:
            get_resp = requests.get(f"http://{replica_address}/get?key={key}&last_applied={last_applied}")
        if not after_delete:
            if get_resp.status_code != 200:
                failed_status_code(200, get_resp.status_code)
            if get_resp.json()[key] != value:
                failed_value(value, get_resp.json()[key])
        else:
            if get_resp.status_code != 404:
                failed_status_code(404, get_resp.status_code)


    time.sleep(0.5)

    #
    # start of the test
    #
    try:
        leader_resp = requests.get('http://localhost:14501/leader')
        if leader_resp.status_code != 200:
            print(f"failed to get leader, response: {leader_resp.text}")
            finish_test(False)
        leader_id, leader_address = leader_resp.json()['leader_id'], leader_resp.json()['address']

        key = 'test_key'
        value = 'test_value'

        #
        # create key
        #
        create_resp = requests.post(f"http://{leader_address}/create?key={key}&value={value}", allow_redirects=False)
        if create_resp.status_code != 200:
            failed_status_code(200, create_resp.status_code)
        check_get_from_replica(leader_address, key, value)

        #
        # update key
        #
        new_value = 'new_test_value'

        update_resp = requests.put(f"http://{leader_address}/update?key={key}&value={new_value}", allow_redirects=False)
        if update_resp.status_code != 200:
            failed_status_code(200, update_resp.status_code)
        check_get_from_replica(leader_address, key, new_value)

        #
        # create key (failed)
        #
        create_resp = requests.post(f"http://{leader_address}/create?key={key}&value={value}", allow_redirects=False)
        if create_resp.status_code != 400:
            failed_status_code(400, create_resp.status_code)

        #
        # CAS
        #
        cas_resp = requests.put(f"http://{leader_address}/cas?key={key}&expected={new_value}&desired={value}", allow_redirects=False)
        if cas_resp.status_code != 200:
            failed_status_code(200, cas_resp.status_code)
        check_get_from_replica(leader_address, key, value)

        #
        # CAS (repeated, failed)
        #
        cas_resp = requests.put(f"http://{leader_address}/cas?key={key}&expected={new_value}&desired={value}", allow_redirects=False)
        if cas_resp.status_code != 400:
            failed_status_code(400, cas_resp.status_code)

        #
        # delete key
        #
        delete_resp = requests.delete(f"http://{leader_address}/delete?key={key}", allow_redirects=False)
        if delete_resp.status_code != 200:
            failed_status_code(200, delete_resp.status_code)
        check_get_from_replica(leader_address, key, value, True)

        print("simple test passed")
    except Exception as e:
        print(f"caught exception: {e}")
        finish_test(False)

    finish_test(True)

if __name__ == "__main__":
    main()
