%function write_wind_into_netCDF(GRID_X, GRID_Y, uwnd, vwnd, pres, TCcen, time, file_name)
function write_wind_into_netCDF(GRID_X, GRID_Y, uwnd, vwnd, pres, time, file_name)

% Source: Xiaohui Zhou;
% InputVar: GRID_X, GRID_Y, uwnd, vwnd, time, file_name;
% Note: the input time vector needs to be referenced to 1900-01-01 00:00:00; 
%       It is a julian day.
% Correction: 
%  X.Chen: change datatype from float (Single) to double, otherwise, the time
%  generated in the netCDF file will be off 
 ncfile1='Ian_HBL_10min.nc';
GRID_X=ncread(ncfile1,'longitude');
GRID_Y=ncread(ncfile1,'latitude');
uwnd=ncread(ncfile1,'uwnd');
vwnd=ncread(ncfile1,'vwnd');
pres=ncread(ncfile1,'P');
time=ncread(ncfile1,'time');
file_name='Ian_HBL_10min_correct_time.nc';

ncid = netcdf.create(file_name,'NC_WRITE');
%Define the dimensions
%[NY,NX]=size(GRID_X);
dimidt = netcdf.defDim(ncid,'time', netcdf.getConstant('NC_UNLIMITED'));
dimidlat = netcdf.defDim(ncid,'lat',length(GRID_Y));
dimidlon = netcdf.defDim(ncid,'lon',length(GRID_X));

%Define IDs for the dimension variables (pressure,time,latitude,...)
date_ID=netcdf.defVar(ncid,'time','NC_DOUBLE',netcdf.getConstant('NC_UNLIMITED'));
latitude_ID=netcdf.defVar(ncid,'latitude','NC_DOUBLE',[dimidlat]);
longitude_ID=netcdf.defVar(ncid,'longitude','NC_DOUBLE',[dimidlon]);
% j_ID=netcdf.defVar(ncid,'j','float',[dimidj]);
% i_ID=netcdf.defVar(ncid,'i','float',[dimidi]);

%Define the main variable ()
uas_ID = netcdf.defVar(ncid,'uwnd','NC_DOUBLE',[dimidlon dimidlat dimidt]);
vas_ID = netcdf.defVar(ncid,'vwnd','NC_DOUBLE',[dimidlon dimidlat dimidt]);
 pas_ID = netcdf.defVar(ncid,'P','NC_DOUBLE',[dimidlon dimidlat dimidt]);
% TCx_ID = netcdf.defVar(ncid,'TClon','NC_DOUBLE',[dimidt]);
% TCy_ID = netcdf.defVar(ncid,'TClat','NC_DOUBLE',[dimidt]);
%density_ID = netcdf.defVar(ncid,'density','double',netcdf.getConstant('NC_UNLIMITED'));
%We are done defining the NetCdf
netcdf.endDef(ncid);
%Then store the dimension variables in
netcdf.putVar(ncid,date_ID,0,length(time), time);
netcdf.putVar(ncid,latitude_ID,GRID_Y);
netcdf.putVar(ncid,longitude_ID,GRID_X);
%Then store my main variable
netcdf.putVar(ncid,uas_ID,uwnd);
netcdf.putVar(ncid,vas_ID,vwnd);
 netcdf.putVar(ncid,pas_ID,pres);
% netcdf.putVar(ncid,TCx_ID,TCcen.x);
% netcdf.putVar(ncid,TCy_ID,TCcen.y);
%
%We're done, close the netcdf
netcdf.close(ncid);
ncwriteatt(file_name,'uwnd','corrdinates','lon lat time');
ncwriteatt(file_name,'uwnd','long_name','Eastward Near-Surface Wind Speed');
ncwriteatt(file_name,'uwnd','units','m s^-1');
ncwriteatt(file_name,'uwnd','standard_name','eastward_wind')
ncwriteatt(file_name,'uwnd','_FillValue',1.000000020040877e+20);
ncwriteatt(file_name,'uwnd','missing_value',1.000000020040877e+20);

ncwriteatt(file_name,'vwnd','corrdinates','lon lat time');
ncwriteatt(file_name,'vwnd','long_name','northward Near-Surface Wind Speed');
ncwriteatt(file_name,'vwnd','units','m s^-1');
ncwriteatt(file_name,'vwnd','standard_name','northward_wind')
ncwriteatt(file_name,'vwnd','_FillValue',1.000000020040877e+20);
ncwriteatt(file_name,'vwnd','missing_value',1.000000020040877e+20);

% put in pressure:
ncwriteatt(file_name,'P','corrdinates','lon lat time');
ncwriteatt(file_name,'P','long_name','pressure at sea level (Holland)');
ncwriteatt(file_name,'P','units','Pscal');
ncwriteatt(file_name,'P','standard_name','surface_pressure')
ncwriteatt(file_name,'P','_FillValue',1.000000020040877e+20);
ncwriteatt(file_name,'P','missing_value',1.000000020040877e+20);

% put in location of the TC center:
% ncwriteatt(file_name,'TClon','corrdinates','time');
% ncwriteatt(file_name,'TClon','long_name','longitude of TC center');
% ncwriteatt(file_name,'TClon','units','degree');
% ncwriteatt(file_name,'TClon','standard_name','TC_lon')
% ncwriteatt(file_name,'TClon','_FillValue',1.000000020040877e+20);
% ncwriteatt(file_name,'TClon','missing_value',1.000000020040877e+20);
% 
% ncwriteatt(file_name,'TClat','corrdinates','time');
% ncwriteatt(file_name,'TClat','long_name','latitude of TC center');
% ncwriteatt(file_name,'TClat','units','degree');
% ncwriteatt(file_name,'TClat','standard_name','TC_lat')
% ncwriteatt(file_name,'TClat','_FillValue',1.000000020040877e+20);
% ncwriteatt(file_name,'TClat','missing_value',1.000000020040877e+20);


ncwriteatt(file_name,'time','units','days since 1900-01-01 00:00:00');
ncwriteatt(file_name,'time','calendar','gregorian');
ncwriteatt(file_name,'time','long_name','Time');
ncwriteatt(file_name,'time','cartesian_axis','T');

ncwriteatt(file_name,'longitude','units','degrees_east');
ncwriteatt(file_name,'longitude','calendar','gregorian');
ncwriteatt(file_name,'longitude','long_name','longitude');
ncwriteatt(file_name,'longitude','standard_name','longitude');
ncwriteatt(file_name,'longitude','bounds','lon_bnds');

ncwriteatt(file_name,'latitude','units','degrees_north');
ncwriteatt(file_name,'latitude','calendar','gregorian');
ncwriteatt(file_name,'latitude','long_name','latitude');
ncwriteatt(file_name,'latitude','standard_name','latitude');
ncwriteatt(file_name,'latitude','bounds','lat_bnds');
%We're done, close the netcdf
ncdisp(file_name)

return