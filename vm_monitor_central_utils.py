from datetime import datetime

from rcsdb.connection import rcsdb_session
from rcsdb.models import VM, VMLoad, GPULoad

from pprint import pprint

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

IP_ADDR = 'ip_address'
VM_ID = 'vm_id'
START_DATE = 'start_date'
END_DATE = 'end_date'

PORT_NUMBER = 8088

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def latest_vm_load_update(vm_id: int) -> datetime:

    with rcsdb_session() as sess:

        vm_load_rows = sess.query(VMLoad).filter(VMLoad.vm_id == vm_id).all()

        latest_date = datetime(2024, 1, 1)

        for row in vm_load_rows:
            if row.timestamp > latest_date:
                latest_date = row.timestamp

    return latest_date.date()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def latest_gpu_load_update(vm_id: int) -> datetime:

    with rcsdb_session() as sess:

        gpu_load_rows = sess.query(GPULoad).filter(GPULoad.vm_id == vm_id).all()

        latest_date = datetime(2024, 1, 1)

        for row in gpu_load_rows:
            if row.timestamp > latest_date:
                latest_date = row.timestamp

    return latest_date.date()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def latest_load_update(vm: VM) -> datetime:


    last_vm_date = latest_vm_load_update(vm.id)
    last_gpu_date = latest_gpu_load_update(vm.id)

    if not vm.gpu:
        return last_vm_date
    else:
        return min(last_vm_date, last_gpu_date)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_usage_payload(vm: VM) -> dict:

    start_data = latest_load_update(vm)
    end_date = datetime.now().date()

    return {VM_ID: vm.id,
            IP_ADDR: vm.ip,
            START_DATE: start_data.isoformat(),
            END_DATE: end_date.isoformat()}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def calculate_avg_load(cpu_usage: list[dict]) -> float:

    total_usage = sum(cpu['usage_percent'] for cpu in cpu_usage)

    average_usage = 0.0
    if len(cpu_usage) != 0:
        average_usage = total_usage / len(cpu_usage)

    return average_usage

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def add_vm_load_to_database(vm_id: int, load_data: dict):

    with rcsdb_session() as sess:

        # get all existing timestamps for this VM to avoid duplicate entries
        existing_timestamps = set(  timestamp for timestamp, in sess.query(VMLoad.timestamp)
                                .filter(VMLoad.vm_id == vm_id)
                                .all())

        for datum in load_data.get('data', []):
            if datetime.fromisoformat(datum['timestamp']) in existing_timestamps:
                continue
            else:
                vm_load = VMLoad(   vm_id=vm_id,
                                    timestamp=datetime.fromisoformat(datum['timestamp']),
                                    load=calculate_avg_load(datum.get('cpus', [])),
                                    memfree=datum.get('memory', {}).get('used_mb', 0),
                                    diskfree=datum.get('disk', {}).get('used_mb', 0))
                sess.add(vm_load)

        sess.commit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def add_gpu_load_to_database(vm_id: int, load_data: dict):

    with rcsdb_session() as sess:

        # get all existing timestamps for this VM to avoid duplicate entries
        existing_timestamps = set(  timestamp for timestamp, in sess.query(GPULoad.timestamp)
                                    .filter(GPULoad.vm_id == vm_id)
                                    .all())

        for datum in load_data.get('data', []):
            if datetime.fromisoformat(datum['timestamp']) in existing_timestamps:
                continue
            else:
                for gpu in datum.get('gpus', []):
                    gpu_load = GPULoad(   vm_id=vm_id,
                                        timestamp=datetime.fromisoformat(datum['timestamp']),
                                        core_use=gpu.get('usage_percent'),
                                        mem_use=int(gpu.get('memory_used_mb')))
                    sess.add(gpu_load)

        sess.commit()
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def add_load_data_to_database(results : list[tuple[str, str, dict]]):

    for _, vm_id, data in results:
        if type(data) is dict:
            try:
                add_vm_load_to_database(int(vm_id), data)
                add_gpu_load_to_database(int(vm_id), data)
            except Exception as e:
                print(f"Error adding load data for VM ID {vm_id}: {e}")
        else:
            print(f"Error retrieving data for VM ID {vm_id}: {data}")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def display_gather_results(results):

    fail_list = []
    success_list = []

    for vm_ip, vm_id, data in results:
        print(f'VM ID: {vm_id}')

        if type(data) is str:
            print(f'Error retrieving data: {data}')
            fail_list.append((vm_ip))
            print('-'*80)
            continue

        print(f'# of records: {len(data.get("data", []))}')
        print('-'*80)

        if data.get('status', '') != 'success':
            fail_list.append((vm_ip))
        else:
            success_list.append((vm_ip))

    print('Summary:')
    print(f'Total VMs: {len(results)}')
    print(f'Successful VMs: {len(success_list)}')
    print(f'Failed VMs: {len(fail_list)}')
    print('Successful VM IPs:')
    for ip in success_list:
        print(f' - {ip}')
    print('Failed VM IPs:')
    for ip in fail_list:
        print(f' - {ip}')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def display_checkup_results(results: list[tuple[str, int, dict | str]]):

    total_vms = len(results)
    n_reachable_vms = sum(1 for _, status, _ in results if status == 200)
    n_unreachable_vms = total_vms - n_reachable_vms
    reachable_vm_ips = []
    unreachable_vm_ips = []

    for ip, status, data in results:
        print(f'VM IP: {ip}')
        print(f'Status: {status}')
        pprint(data)
        print('-'*80)

        if status == 200:
            reachable_vm_ips.append(ip)
        else:
            unreachable_vm_ips.append(ip)

    print('Summary:')
    print(f'Total VMs: {total_vms}')
    print(f'Reachable VMs: {n_reachable_vms}')
    print(f'Unreachable VMs: {n_unreachable_vms}')
    print('Reachable VM IPs:')
    for ip in reachable_vm_ips:
        print(f' - {ip}')

    print('Unreachable VM IPs:')
    for ip in unreachable_vm_ips:
        print(f' - {ip}')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~