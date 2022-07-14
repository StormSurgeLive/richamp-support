function subset_fort63_richamp(indir, outdir)
    %% output directory & filename
    infile='fort.63.nc';
    outfile='RICHAMP_depth.nc';
    lonrange=[-71-54/60 -71-6/60-30/3600]; latrange=[41+8/60+30/3600 42+2/60+30/3600];
    %% read in
    t0unix=datenum([1970 1 1 0 0 0]);            % start of unix time epoch
    ncfile=[indir 'fort.63.nc'];
    x=ncread(ncfile,'x');
    y=ncread(ncfile,'y');
    z=ncread(ncfile,'depth');
    element=ncread(ncfile,'element');
    element2=element';
    clear element
    time=ncread(ncfile,'time');
    bdate = ncreadatt(ncfile,'time','base_date');
    t0=datenum(bdate);
    zeta=ncread(ncfile,'zeta');
    %%  time - needs to be as time_unix for chris - at one point needed to be changed to integer 16 * may not be necessary *
    tstart_unix=86400*(t0-t0unix);     % unix time of model start
    time_unix=uint32(tstart_unix+time);
    %% subset - make grd and then subset
    grd.x=x; grd.y=y; grd.dp=z; grd.nm=element2;
    [x,y,depth,element,nn_new]=subset_dontplot_mesh(grd,lonrange,latrange);
    element=element';
    zeta=zeta(~isnan(nn_new),:); 
    % modify schema of input netcdf file for output
    finfo=ncinfo(strcat(indir,infile));
    finfo.Filename=strcat(outdir,outfile);
    finfo.Dimensions=finfo.Dimensions(1:4); %only need 1st 4 dimensions
    finfo.Dimensions(2).Length=length(x);
    finfo.Variables=finfo.Variables([1:4 16 17]);   % only need certain variables (from elevation file)
    finfo.Variables(7)=finfo.Variables(1);          % new variable time_unix to be created using time as template
    finfo.Variables(2).Dimensions.Length=length(x);
    finfo.Variables(2).Size=length(x);
    finfo.Dimensions(3).Length=length(element(1,:));
    finfo.Variables(3).Dimensions.Length=length(x);
    finfo.Variables(3).Size=length(x);
    finfo.Variables(4).Dimensions(2).Length=length(element(1,:));
    finfo.Variables(4).Size=size(element);
    finfo.Variables(5).Dimensions.Length=length(x);
    finfo.Variables(5).Size=length(x);
    finfo.Variables(6).Dimensions(1).Length=length(x);
    finfo.Variables(6).Size=size(zeta);
    finfo.Variables(7).Name='time_unix';
    finfo.Variables(7).Attributes(1).Value='model time_unix';
    finfo.Variables(7).Attributes(2).Value='time_unix';
    finfo.Variables(7).Attributes(3).Value='seconds since 1970-01-01 00:00:00';
    finfo.Variables(7).Attributes(4).Value='1970-01-01 00:00:00';
    for i = 2:6 % for variables we edit the size of, chunk size must be smaller or equal to size
        if ~isempty(finfo.Variables(i).ChunkSize) % sometimes ChunkSize is empty, and if so we can leave it empty
            for j = 1:numel(finfo.Variables(i).Size)
                if finfo.Variables(i).ChunkSize(j) > finfo.Variables(i).Size(j)
                    finfo.Variables(i).ChunkSize = finfo.Variables(i).Size;
                    break
                end
            end
        end
    end
    if ~exist(strcat(outdir,outfile),'file')
        % create output file if it doesn't exist 
          ncwriteschema(strcat(outdir,outfile),finfo);
    end   
    ncwrite(strcat(outdir,outfile),'time',time);
    ncwrite(strcat(outdir,outfile),'x',x);
    ncwrite(strcat(outdir,outfile),'y',y);
    ncwrite(strcat(outdir,outfile),'element',element);
    ncwrite(strcat(outdir,outfile),'depth',depth);
    ncwrite(strcat(outdir,outfile),'zeta',zeta);
    ncwrite(strcat(outdir,outfile),'time_unix',time_unix);
end
