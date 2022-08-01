# richamp-support

=== ASGS Post-Processing Setup Instructions ===

NOTE: You should already have set up an ASGS instance before you go through this setup. If you haven’t, do that first.

    1. Contact Josh Port (joshua_port@uri.edu) and ask him for the URI MetGet API key. If Josh is unavailable, try reaching out to Zach Cobell (zcobell@thewaterinstitute.org).
    2. Navigate to a directory on hatteras in which you’d like to store your post-processing code.
    3. Run “git clone https://github.com/StormSurgeLive/richamp-support”. This will pull down the latest post-processing code from GitHub. The folder this command creates will henceforth be referred to as the “post-processing directory”.
        1. You may need to do some git configuration if you haven’t used it on hatteras yet. Git should prompt you if so. Just follow the instructions.
        2. If you ever need to pull down updates to the code in the future, you can do this via “git pull”.
    4. Copy the following two NetCDFs from /home/joshua_p/postprocess to your post-processing directory:
        1. gfs-roughness.nc
        2. NLCD_z0_RICHAMP_Reg_Grid.nc
    5. Create an empty directory within your post-processing directory named “metget_temp”.
    6. Open richamp_scale_and_subset.scr in the post-processing directory. Change the “postprocessdir” so that it’s pointing at your post-processing directory. Save and close the file.
    7. Copy richamp_scale_and_subset.scr and richamp_scale_and_subset.sh to your ASGS output directory (i.e. [base ASGS directory]/output).
        1. If these two files are ever updated, you will need to repeat the last two steps.
    8. From within ASGSH run the following:
        1. “pip3 install requests scipy”
        2. “export METGET_API_KEY=[URI MetGet API key from step 1]”
        3. “export METGET_ENDPOINT=https://api.metget.zachcobell.com”
    9. Open your ASGS config file. Add richamp_scale_and_subset.sh to the front of the POSTPROCESS list. Also add RICHAMP_fort63.nc and RICHAMP_wind.nc to the postAdditionalFiles list. Don’t close the file yet.
        1. If you don’t know what your ASGS config file is, run “echo $ASGS_CONFIG” via ASGSH.
    10. createOPeNDAPFileList.sh and $OPENDAPPOST should already be in the POSTPROCESS list, but if not, add those after richamp_scale_and_subset.sh. You’ll also need to add another line above that to set OPENDAPPOST=opendap_post2.sh. Save and close the file. The final configuration might look like this:
        1. OPENDAPPOST=opendap_post2.sh
        2. POSTPROCESS=( richamp_scale_and_subset.sh createOPeNDAPFileList.sh $OPENDAPPOST )
        3. postAdditionalFiles=( RICHAMP_fort63.nc RICHAMP_wind.nc )
    11. You are now set up! Just run ASGS as you would normally.
        1. If you need to troubleshoot, refer to uri_post.err and uri_post.out, which will be generated in the ASGS scenario directory, and richamp_scale_and_subset.sh.log, which will be generated in your ASGS output folder (where you moved your richamp_scale_and_subset.* files to earlier).
        2. If you get stuck or find a bug, contact Josh Port (joshua_port@uri.edu). If Josh is unavailable, try reaching out to Dave Ullman (dullman@uri.edu).
