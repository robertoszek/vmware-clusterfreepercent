#========================================================================
# Created by:  CHAMORR1
# Filename: DSCFreeSpacePercentReservation.ps1
# Usage: DSCFreeSpacePercent.ps1 <VCenterhost> <DataStoreCluster> <requiredSpaceGB> <vmName>
# -VCenterhost   	-> VCenter host
# -DataStoreCluster -> Datastore Cluster Name
# -requiredSpaceGB  -> Required Space for the Server/App to provision
# -vmName           -> Virtual machine name
# This script checks the available space in a Cluster Datastore. 
# Creates a local file to keep track of reserved space by running requests
# It also creates a lock file to mitigate a potential race condition
# This reservations survive hoursElapsed at a maximum
# Only one reservation is allowed for every vmName except if it empty
# Return results:
# ERROR: (Free Datastore Space - Required Space) <=  10% Datastore Free Space
# OK: (Free Datastore Space - Required Space) >  10% Datastore Free Space
#========================================================================

Write-Host "Getting Datastore Info..."
Write-Host " "
Write-Host "- vSphere server : " $args[0]
Write-Host "- Datastorage name        : " $args[1]
Write-Host "- Required Space(GB)        : " $args[2]
Write-Host "- VM Name:            " $args[3]
Write-Host " "

$WarningPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"
Get-Module -ListAvailable VMware* | Import-Module
#Add-PSSnapin vmware.vimautomation.core
$error.clear();

$myDSCluster = $args[1];

echo "Connecting to vSphere..."
$vCenterServer=Connect-VIServer -User <user> -Password <password> -Server $args[0]

if ($vCenterServer -eq $null) {
	echo "There was a problem while connecting to vSphere:"
	echo ""
	$error
	$error.clear();
} else {

	$dsc = Get-DatastoreCluster -Name $myDSCluster
    
	if ($error -like "*Get-DatastoreCluster*") {
		echo "- ERROR: There was an error querying for the Datastore Cluster."
		$error
		$error.clear();
	} else {
		$requiredSpaceGB = $args[2]
        $FreeSpaceGB = $dsc.FreeSpaceGB
        $vSphereServer = $args[0]
        $datastorage = $args[1]

        $reservedSpaceGB = 0
		$vmName = $args[3]
        $reservationFile =  $PSScriptRoot + "\DSCFreeSpacePercentReservation.json"

        echo "Trying to reserve space..."
        if (!(Test-Path $reservationFile)){
            $subReservation = [System.Collections.ArrayList]@()
            $subReservation += [pscustomobject]@{
                "timestamp"="$(Get-Date -format o)";
				'requiredSpaceGB'="$requiredSpaceGB";
				'vmName'="$vmName"
            }
            $subDatastorage = [System.Collections.ArrayList]@()
            $subDatastorage += [pscustomobject]@{
                "reservation"= $subReservation
            }
            $subData = [System.Collections.ArrayList]@()
            $subData += [pscustomobject]@{
                "$datastorage"= $subDataStorage
            }
            $json = [pscustomobject]@{
                "$vSphereServer" = $subData
            }
            $boilerplate = $json | ConvertTo-Json -Depth 9
            New-Item -path $reservationFile -type File -value $boilerplate
            Write-Host "Created new file"
            $reservedSpaceGB = $requiredSpaceGB
        }
        else{
            $lockPath= $PSScriptRoot + "\DSCFreeSpacePercentReservation.lck"
			$timeout = New-TimeSpan -Seconds 120
			$endTime = (Get-Date).Add($timeout)
			$hoursElapsed = 8
            do {
                $result = Test-Path $lockPath
                Write-Host "Waiting for lock..."
                Start-Sleep 5
            }until ($result -eq $False -or ((Get-Date) -gt $endTime))
            try{
                New-Item -path $lockPath -type File
            }
            catch{
                Write-Host "Time elapsed, giving up..."
                Write-Host "Deleting stuck lock..."
                Remove-Item -Path $lockPath
                New-Item -path $lockPath -type File
            }
            
            $reservationJson = ConvertFrom-Json (Get-Content -Raw $reservationFile)
            if ($reservationJson.$vSphereServer.$dataStorage.reservation -eq $null){
                $subReservation = [System.Collections.ArrayList]@()
            }else{
                [System.Collections.ArrayList]$subReservation = $reservationJson.$vSphereServer.$dataStorage.reservation
			}
			
            $Time2 = Get-Date -Format o
            # Delete entries older than hoursElapsed and repeated vmName            
            for ($i = 0; $i -lt $subReservation.Count ; $i++) {
                $Time1 = $subReservation[$i].timestamp
                $TimeDiff = New-TimeSpan $Time1 $Time2
                if($TimeDiff.TotalHours -ge $hoursElapsed){
                    $subReservation.RemoveAt($i)
                    $i--
                }elseif($vmName -eq $subReservation[$i].vmName -and $vmName -ne "") {
					$subReservation.RemoveAt($i)
                    $i--
				}
            }

            $subReservation += [pscustomobject]@{
                "timestamp"="$(Get-Date -format o)";
				'requiredSpaceGB'="$requiredSpaceGB";
				'vmName'="$vmName"
            }
            
            if ($reservationJson.$vSphereServer.$dataStorage -eq $null){
                $subDatastorage = [System.Collections.ArrayList]@()

            }
            $subDatastorage += [pscustomobject]@{
                "reservation"= $subReservation
            }
            $reservationJson.$vSphereServer.$dataStorage | Add-Member -Value $subReservation -Name reservation -MemberType NoteProperty -Force -ErrorAction Ignore
            

            if ($reservationJson.$vSphereServer.$dataStorage -eq $null){
                $subData = [System.Collections.ArrayList]@()  
            }
            $subData += [pscustomobject]@{
                "$datastorage"= $subDataStorage
            }
            $reservationJson.$vSphereServer | Add-Member -Value $subDatastorage -Name $dataStorage -MemberType NoteProperty -ErrorAction Ignore

            $reservationJson | Add-Member -Value $subData -Name "$vSphereServer" -MemberType NoteProperty -ErrorAction Ignore


            # Add up reservation space
            for ($i = 0; $i -lt $reservationJson.$vSphereServer.$dataStorage.reservation.Count ; $i++) {
                $reservedSpaceGB += $reservationJson.$vSphereServer.$dataStorage.reservation[$i].requiredSpaceGB
            }
            # If everything fails at least don't let provision machines for free
            if($reservedSpaceGB -eq 0){
                $reservedSpaceGB = $requiredSpaceGB
            }
            
            $reservationJson | ConvertTo-Json -depth 100 | Out-File $reservationFile              

            Write-Host "File already exists and new text content added"
            Write-Host "Deleting lock..."
            
            
            if (Test-Path $lockPath){
                Remove-Item -Path $lockPath
            }
            
        }

		$FreeSpaceGBAfter = $FreeSpaceGB - $reservedSpaceGB
		$CapacityGB = $dsc.CapacityGB
		$DSCFreePercent = ($FreeSpaceGB / $CapacityGB) * 100
		$DSCFreePercentAfter = (($FreeSpaceGB - $reservedSpaceGB) / $CapacityGB) * 100
		
		$DSCFreePercent = "{0:N2}" -f $DSCFreePercent
		$DSCFreePercentAfter = "{0:N2}" -f $DSCFreePercentAfter

        echo "Required Space(GB) : " $requiredSpaceGB
        echo "Reserved Space(GB) : " $reservedSpaceGB
		echo "DSCluster Free Space(GB) : " $FreeSpaceGB	
		echo "DSCluster Free Space after provisioning(GB) : " $FreeSpaceGBAfter	
		echo "DSCluster Capacity(GB) : " $CapacityGB
		echo "DSCluster free space percent : " $DSCFreePercent
		echo "DSCluster free space percent after provisioning : " $DSCFreePercentAfter
        
        
		if ( ($FreeSpaceGBAfter -gt 0) -and ($DSCFreePercentAfter -gt 10)){
			Write-Host "OK, free percent after provisioning: " $DSCFreePercentAfter
		} else {
			Write-Host "ERROR: Cluster datastore free space percent not enough for provisioning. We can't continue with the process."
		}
	}
}
echo "Disconnecting from vSphere..."
$error.clear();
Disconnect-VIServer $vCenterServer -confirm:$false;