# richamp-support

## ASGS Post-Processing Setup Instructions on Hatteras & Unity

NOTE: You should already have set up an ASGS instance before you go through this setup. If you haven’t, do that first.

1. Contact Josh Port (joshua_port@uri.edu) and ask him for the URI MetGet API key. If Josh is unavailable, try reaching out to Zach Cobell (zcobell@thewaterinstitute.org).
2. Navigate to the output subfolder within your main ASGS directory (i.e. SCRIPTDIR/output)
3. Run “git clone git@github.com:StormSurgeLive/richamp-support”. This will pull down the latest post-processing code from GitHub. The folder this command creates will henceforth be referred to as the “post-processing directory”.
   - You should have already set up SSH keys for GitHub when you configured ASGS, but if not use “git clone https://github.com/StormSurgeLive/richamp-support” instead. You may also need to do some git configuration if you haven’t used it on hatteras yet. Git should prompt you if so. Just follow the instructions.
   - If you ever need to pull down updates to the code in the future, you can do this via “git pull”.
4. Copy the following two NetCDFs from /home/joshua_p/postprocess (Hatteras) or /work/pi_iginis_uri_edu/joshua_port_uri_edu/postprocess (Unity) to your richamp-support directory:
   - gfs-roughness.nc
   - NLCD_z0_RICHAMP_Reg_Grid.nc
5. Copy the following two files from /projects/ees/dhs-crc/dcrowley/c_PWM/b_RIC_TEST (Hatteras) or /work/pi_iginis_uri_edu/joshua_port_uri_edu/postprocess (Unity) to your richamp-support directory:
   - diag_parm.nml
   - windgfdl
6. From within ASGSH run the following:
   - “pip3 install pandas pyproj requests scipy”
   - “export METGET_API_KEY=[URI MetGet API key from step 1]”
   - “export METGET_ENDPOINT=https://api.metget.zachcobell.com”
7. Open your ASGS config file
   - If you don’t know what your ASGS config file is, run “echo $ASGS_CONFIG” via ASGSH.
8. Add "richamp-support/richamp_scale_and_subset.sh" to the front of the POSTPROCESS list. (Hatteras only through the end of #8) Also add RICHAMP_fort63.nc and RICHAMP_wind.nc to the postAdditionalFiles list. createOPeNDAPFileList.sh and $OPENDAPPOST should already be in the POSTPROCESS list, but if not, add those after richamp_scale_and_subset.sh and add another line above that to set OPENDAPPOST=opendap_post2.sh. Save and close the file. The final configuration might look like this:
   - OPENDAPPOST=opendap_post2.sh
   - POSTPROCESS=( richamp-support/richamp_scale_and_subset.sh createOPeNDAPFileList.sh $OPENDAPPOST )
   - postAdditionalFiles=( RICHAMP_fort63.nc RICHAMP_wind.nc )
9. (Hatteras only) Open richamp_scale_and_subset.scr. Make the following changes:
   - Uncomment the "##SBATCH --constraint=hatteras" and "##SBATCH -p lowpri" lines (i.e. change them from ## to #; one # is still needed)
   - Comment out the "#SBATCH -p uri-cpu" line
   - Comment out the entire "upload file to s3" section near the bottom
   - Either update output_dir to a directory to which the output files should be copied, or comment out the relevant cp command if you don't need the files to be copied
10. (Unity only, optional) Download the latest s3cmd release from https://github.com/s3tools/s3cmd and unpack the s3cmd files into your ~/bin folder. If this folder does not exist, create it.
    - Only necessary if you wish to upload files to an S3 bucket, which can be configured via the commented-out code in richamp_scale_and_subset.scr.
11. (Unity only, optional) Reach out to Josh Port (joshua_port@uri.edu) for the RICHAMP S3 bucket name, endpoint address, and credentials. If Josh is unavailable, reach out to Kevin Bryan (bryank@uri.edu). Once you have them, run "s3cmd --configure" and use that information to set up s3cmd. Use no encryption & password and HTTPS. 
    - Only necessary if you wish to upload files to an S3 bucket, which can be configured via the commented-out code in richamp_scale_and_subset.scr.
12. (Unity only, optional) If you intend to use cp instead of S3, ensure that the output_dir in richamp_scale_and_subset.scr is set appropriately. This folder should exist and be unique to an ASGS instance so files from different instances never overwrite each other. So, if you're configuring this post-processing code as part of a new instance, you may want to create another output folder and use that as your output_dir.
13. You are now set up! Just run ASGS as you would normally.
    - If you need to troubleshoot, refer to uri_post.err and uri_post.out, which will be generated in the ASGS scenario directory, and richamp_scale_and_subset.sh.log, which will be generated in the richamp-support folder.
    - If you get stuck or find a bug, contact Josh Port (joshua_port@uri.edu). If Josh is unavailable, try reaching out to Dave Ullman (dullman@uri.edu).
