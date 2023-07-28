#!/bin/bash
logfile=${0}.log
targetScript="richamp_scale_and_subset.scr"
jobCheckIntervalSeconds=15
for ending in submit start finish error ; do
    rm -f $targetScript.$ending # remove .submit .start .finish and .error if they are left over
done
#
echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] $0: Submitting $targetScript $logfile" > $targetScript.submit | tee --append $logfile
sbatch richamp-support/$targetScript $logfile 2>>jobErr >jobID
# check to see if the sbatch command succeeded; you can also add a retry
# but maybe not necessary
if [[ $? == 0 ]]; then
    echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] $0: Job ID for $targetScript is $(<jobID)" >> $logfile
else
    echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] $0: The sbatch command failed for $targetScript." >> $logfile
    exit
fi
# wait for batch job to start
until [[ -e $targetScript.start ]]; do
    echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] Waiting for $targetScript to start." >> $logfile
    sleep $jobCheckIntervalSeconds
done
echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] The batch job for $targetScript has started." >> $logfile
# wait for batch job to finish successfully or exit with an error
until [[ -e $targetScript.finish || -e $targetScript.error ]]; do
    echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] Waiting for $targetScript to finish." >> $logfile
    sleep $jobCheckIntervalSeconds
done
echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] The batch job for $targetScript has exited." >> $logfile
