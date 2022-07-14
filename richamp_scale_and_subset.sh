#!/bin/bash

asgs_python=$(which python3) # jgf: I don't think you need this
# jgf: the next 3 lines are probably not needed,
# the ASGS will execute the post processing in $SCENARIODIR,
# i.e., it will be the current working directory when this
# script is executed
ADVISDIR=$2
ENSTORM=$7
SCENARIODIR=$ADVISDIR/$ENSTORM # Should also be PWD, but I would rather not assume; ENSTORM should be the same as SCENARIO (used to form SCENARIODIR elsewhere)
#
logfile=${0}.log
targetScript="richamp_scale_and_subset.scr"
jobCheckIntervalSeconds=60
for ending in submit start finish error ; do
    rm -f $targetScript.$ending # remove .submit .start .finish and .error if they are left over
done
#
echo "[$(date +'%Y-%h-%d-T%H:%M:%S%z')] $0: Submitting $targetScript $asgs_python $SCENARIODIR" > $targetScript.submit | tee --append $logfile
sbatch $targetScript $asgs_python $SCENARIODIR 2>>jobErr >jobID
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