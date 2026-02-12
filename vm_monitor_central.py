from pprint import pprint
import asyncio
import logging
import aiohttp
import ipaddress
import argparse

from vm_monitor_central_utils import *
import requests

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vm_monitor_central.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def check_vm_status(session, ip):
    try:
        # Validate IP address format
        ipaddress.ip_address(ip)
        async with session.get(f'http://{ip}:{PORT_NUMBER}/check_up', timeout=5) as response:
            data = await response.json()
            return ip, response.status, data
    except Exception as e:
        return ip, -1, f'Error: {e}'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def check_all_vms() -> list[tuple[str, int, dict | str]]:

    with rcsdb_session() as sess:
        vm_ips = [vm.ip for vm in sess.query(VM).filter(VM.deleted.is_(None)).all()]

    async with aiohttp.ClientSession() as session:
        tasks = [check_vm_status(session, ip) for ip in vm_ips]
        results = await asyncio.gather(*tasks)
        return results

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_one_vm(ip: str) -> tuple[str, int, dict | str]:

    try:
        request_str = f'http://{ip}:{PORT_NUMBER}/check_up'

        logger.info(f'Request URL: {request_str}')

        response = requests.get(request_str, timeout=5, proxies={'http': None, 'https': None})
        status_code = response.status_code
        data = response.json()
        logger.info(f'Usage data from {ip} (Status: {status_code})')

        return ip, data

    except Exception as e:
        logger.info(f'Error fetching usage data from {ip} : {e}')
        return ip, f'Error: {e}'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def get_vm_usage_data(session,
                            payload: dict) -> tuple[str, str, dict]:

    try:
        # Validate IP address format
        ipaddress.ip_address(payload[IP_ADDR])
        request_str = f'http://{payload[IP_ADDR]}:{PORT_NUMBER}/get_usage_data?start={payload[START_DATE]}&end={payload[END_DATE]}'

        logger.info(f'Request URL: {request_str}')

        async with session.get(request_str, timeout=5) as response:
            status_code = response.status
            data = await response.json()
            logger.info(f'Usage data from {payload[IP_ADDR]} (Status: {status_code})')
            return payload[IP_ADDR], payload[VM_ID], data

    except Exception as e:
        logger.info(f'Error fetching usage data from {payload[IP_ADDR]} : {e}')
        return payload[IP_ADDR], payload[VM_ID], f'Error: {e}'
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def get_all_vm_usage_data() -> list[tuple[str, dict]]:

    with rcsdb_session() as sess:
        usage_payloads = [get_usage_payload(vm) for vm in sess.query(VM).filter(VM.deleted.is_(None)).all()]

        async with aiohttp.ClientSession() as session:

            tasks = [get_vm_usage_data(session, payload) for payload in usage_payloads]
            results = await asyncio.gather(*tasks)

            return results

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_one_vm_usage_data(ip: str):

    with rcsdb_session() as sess:
        vm = sess.query(VM).filter(VM.deleted.is_(None) & (VM.ip == ip)).first()

        if not vm:
            logger.info(f'No active VM found with IP: {ip}')
            return None

        payload = get_usage_payload(vm)

        try:
            # Validate IP address format
            ipaddress.ip_address(payload[IP_ADDR])
            request_str = f'http://{payload[IP_ADDR]}:{PORT_NUMBER}/get_usage_data?start={payload[START_DATE]}&end={payload[END_DATE]}'

            logger.info(f'Request URL: {request_str}')

            response = requests.get(request_str, timeout=5,proxies={'http': None, 'https': None})
            status_code = response.status_code
            data = response.json()
            logger.info(f'Usage data from {payload[IP_ADDR]} (Status: {status_code})')
            return payload[IP_ADDR], payload[VM_ID], data

        except Exception as e:
            logger.info(f'Error fetching usage data from {payload[IP_ADDR]} : {e}')
            return payload[IP_ADDR], payload[VM_ID], f'Error: {e}'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def purge_old_data(session,
                         ip: str,
                         num_days: int) -> tuple[str, dict | str]:

    try:
        # Validate IP address format
        ipaddress.ip_address(ip)
        async with session.post(f'http://{ip}:{PORT_NUMBER}/purge?days={num_days}', timeout=5) as response:
            data = await response.json()
            logger.info(f'Purge response from {ip}: {data}')
            return ip, data
    except Exception as e:
        return ip, f'Error: {e}'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def purge_all_old_data(num_days: int = 30) -> list[tuple[str, dict | str]]:

    with rcsdb_session() as sess:
        vm_ips = [vm.ip for vm in sess.query(VM).filter(VM.deleted.is_(None)).all()]

    async with aiohttp.ClientSession() as session:
        tasks = [purge_old_data(session, ip, num_days) for ip in vm_ips]
        results = await asyncio.gather(*tasks)
        return results

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():

    parser = argparse.ArgumentParser(description='VM Monitor Central')
    parser.add_argument('--gather_one', type=str, metavar='IP', help='Gather usage data from a specific VM by IP address')
    parser.add_argument('--gather_all', action='store_true', help='Gather usage data from all VMs')
    parser.add_argument('--purge_one', type=str, nargs=2, metavar=('IP', 'NUM_DAYS'), help='Purge old data for a specific VM by IP address')
    parser.add_argument('--purge_all', metavar='NUM_DAYS', type=int, help='Purge old data')
    parser.add_argument('--checkup_one', type=str, metavar='IP', help='Check status of a specific VM by IP address')
    parser.add_argument('--checkup_all', action='store_true', help='Check status of all VMs')

    args = parser.parse_args()

    if args.gather_all:
        results = asyncio.run(get_all_vm_usage_data())
        add_load_data_to_database(results)
        display_gather_results(results)
    elif args.gather_one:
        results = get_one_vm_usage_data(args.gather_one)
        add_load_data_to_database([results])
        display_gather_results([results])
    elif args.purge_all:
        asyncio.run(purge_all_old_data(num_days=args.purge_all))
    elif args.purge_one:
        pass
    elif args.checkup_one:
        result = check_one_vm(args.checkup_one)
        print(f'VM IP: {result[0]}')
        print(f'Status: {result[1]}')
    else:
        results = asyncio.run(check_all_vms())
        display_checkup_results(results)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == '__main__':
    main()
