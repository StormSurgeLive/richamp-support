#!/bin/bash
logfile=${0}.log
targetScript="richamp_scale_and_subset_post_init.scr"
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
