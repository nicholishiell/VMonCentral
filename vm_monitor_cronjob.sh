#!/bin/bash
source /home/sysadmin/cloudman/.venv/bin/activate
python /home/sysadmin/cloudman/VMon/VMonCentral/vm_monitor_central.py --gather_all
#python /home/sysadmin/cloudma/VMon/VMonCentral/vm_monitor_central.py --purge_all 30
