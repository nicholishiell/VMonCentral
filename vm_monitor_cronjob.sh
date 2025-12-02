#!/bin/bash
source /home/sysadmin/VMon/VMonCentral/.venv/bin/activate
python /home/sysadmin/VMon/VMonCentral/vm_monitor_central.py --gather_all
#python /home/sysadmin/VMon/VMonCentral/vm_monitor_central.py --purge_all 30
