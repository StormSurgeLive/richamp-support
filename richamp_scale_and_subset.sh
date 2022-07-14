#!/bin/bash

asgs_python=$(which python3)
ADVISDIR=$2
ENSTORM=$7
SCENARIODIR=$ADVISDIR/$ENSTORM # Should also be PWD, but I would rather not assume; ENSTORM should be the same as SCENARIO (used to form SCENARIODIR elsewhere)
sbatch richamp_scale_and_subset.scr $asgs_python $SCENARIODIR
