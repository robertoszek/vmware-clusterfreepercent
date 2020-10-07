Script to find out how much space is available in a vSphere datastore cluster. It keeps track of the reserved space (by grouping it by vmName) on that particular cluster by writing on DSCFreeSpacePercentReservation.json.
Implementations on Python and PowerShell are available.

## Usage


### DSCFreeSpacePercent\.py

NOTE: pyvmomi module is needed for the Python version. Create a virtual environment and intall it with pip ```(venv) pip install pyvmomi```

```console
usage: DSCFreeSpacePercent.py [-h] -s HOST [-o PORT] [-u USER] [-p PASSWORD] -d DSCLUSTER -r REQUIREDSPACE [-t TIME]
```

```powershell
(venv) C:\path\to\venv> venv\Scripts\python.exe DSCFreeSpacePercent.py -s ${VCenterHost} -d ${ClusterDataStore} -r ${TotalSizeGB}
```
Example:

```powershell
(venv) C:\path\to\venv> venv\Scripts\python.exe DSCFreeSpacePercent.py -s vcenter.contoso.com -d CLUSTER_NAME -r 370.0
```

### DSCFreeSpacePercent.ps1
```powershell
 powershell -ExecutionPolicy bypass -f DSCFreeSpacePercent.ps1 ${VCenterHost} ${ClusterDataStore} ${TotalSizeGB} ${vmName}
```
Example:
```powershell
powershell -ExecutionPolicy bypass -f DSCFreeSpacePercent.ps1 vcenter.contoso.com CLUSTER_NAME 370.0
```

Example of generated JSON:
```json
{
   "testvcenter": [
      {
         "CLUSTER1": [
            {
               "reservation": [
                  {
                     "timestamp": "2020-04-28T09:35:37.0746668+02:00",
                     "requiredSpaceGB": "370.0",
                     "vmName": "myVM"
                  }
               ]
            }
         ]
      }
   ],
   "vcenter2.contoso.com": [
      {
         "CLUSTER_2": [
            {
               "reservation": [
                  {
                     "timestamp": "2020-04-29T09:46:16.1407379+02:00",
                     "requiredSpaceGB": "992.0",
                     "vmName": "myVM2"
                  }
               ]
            }
         ],
         "CLUSTER_3": [
            {
               "reservation": [
                  {
                     "timestamp": "2020-04-29T12:53:42.5856768+02:00",
                     "requiredSpaceGB": "992.0",
                     "vmName": "myVM2"
                  },
                  {
                     "timestamp": "2020-04-29T12:58:06.8931503+02:00",
                     "requiredSpaceGB": "150.0",
                     "vmName": ""
                  },
                  {
                     "timestamp": "2020-04-29T13:02:23.5545745+02:00",
                     "requiredSpaceGB": "900.0",
                     "vmName": ""
                  },
                  {
                     "timestamp": "2020-04-29T13:05:18.8776620+02:00",
                     "requiredSpaceGB": "240.0",
                     "vmName": "myTotallyOriginalName"
                  }
               ]
            }
         ]
      }
   ]
}
```
