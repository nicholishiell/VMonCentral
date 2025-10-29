from datetime import datetime

from rcsdb.connection import session as rcsdb_session
from rcsdb.models import VM, VMLoad, GPULoad

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

IP_ADDR = 'ip_address'
VM_ID = 'vm_id'
START_DATE = 'start_date'
END_DATE = 'end_date'

PORT_NUMBER = 8088

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def latest_vm_load_update(vm_id: int) -> datetime:
    vm_load_rows = rcsdb_session.query(VMLoad).filter(VMLoad.vm_id == vm_id).all()

    latest_date = datetime(2024, 1, 1)

    for row in vm_load_rows:
        if row.timestamp > latest_date:
            latest_date = row.timestamp

    return latest_date.date()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def latest_gpu_load_update(vm_id: int) -> datetime:
    gpu_load_rows = rcsdb_session.query(GPULoad).filter(GPULoad.vm_id == vm_id).all()

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
    avg_usage = total_usage / len(cpu_usage)

    return avg_usage

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def add_vm_load_to_database(vm_id: int, load_data: dict):

    # get all existing timestamps for this VM to avoid duplicate entries
    existing_timestamps = set(  timestamp for timestamp, in rcsdb_session.query(VMLoad.timestamp)
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
            rcsdb_session.add(vm_load)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def add_gpu_load_to_database(vm_id: int, load_data: dict):

    # get all existing timestamps for this VM to avoid duplicate entries
    existing_timestamps = set(  timestamp for timestamp, in rcsdb_session.query(GPULoad.timestamp)
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
                rcsdb_session.add(gpu_load)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def add_load_data_to_database(results : list[tuple[str, dict]]):

    for vm_id, data in results:
        if 'Error' in data:
            continue

        vm = rcsdb_session.query(VM).filter(VM.id == vm_id).first()

        if not vm:
            continue

        add_vm_load_to_database(int(vm_id), data)

        add_gpu_load_to_database(int(vm_id), data)

    rcsdb_session.commit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~