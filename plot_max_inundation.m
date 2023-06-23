function plot_max_inundation(indir, outdir, nc_rough, scenario)
    % Sanitize input
    if indir(end) ~= '/'
        indir = strcat(indir,'/');
    end
    if outdir(end) ~= '/'
        outdir = strcat(outdir,'/');
    end
    if scenario == "forecast"
        scen_label = 'Center-Track';
    elseif scenario == "veerLeftEdge"
        scen_label = 'Left-Edge-Track';
    elseif scenario == "veerRightEdge"
        scen_label = 'Right-Edge-Track';
    end

    % Specify file names
    infile = strcat(indir,'fort.63.nc');
    outfile = strcat(outdir,'RICHAMP_max_inundation');
    
    % Set variables from infile
    longitude = ncread(infile,'x');
    latitude = ncread(infile,'y');
    element = ncread(infile,'element'); %contains triangular grid node information
    ssh = ncread(infile,'zeta');
    t = ncread(infile,'time');
    
    % Convert t to datetime
    units = ncreadatt(infile,'time','units');
    base_date = datetime(ncreadatt(infile,'time','base_date'));
    if contains(units,'seconds')
        t = base_date + seconds(t);
    elseif contains(units,'minutes')
        t = base_date + minutes(t);
    elseif contains(units,'days')
        t = base_date + days(t);
    end

    % For plotting shoreline
    [lon_rough, lat_rough] = ndgrid(ncread(nc_rough,'lon'), ncread(nc_rough,'lat')); 
    land_rough = ncread(nc_rough,'land_rough');
    is_water = double(land_rough <= .0031); % Water should be .003
    
    % Load state borders
    states = readgeotable("usastatehi.shp");
    
    % Aspect ratio
    lon_min = lon_rough(1,1);
    lon_max = lon_rough(end,end);
    lat_min = lat_rough(1,1);
    lat_max = lat_rough(end,end);
    lat_mid = (lat_min + lat_max) / 2;
    rad_earth = 6371009;
    onedeglon = 2 * rad_earth * cosd(lat_mid) * pi / 360;
    onedeglat = 2 * rad_earth * pi / 360;
    
    % Find magnitude of maximum SSH at each node for the plot
    [max_per_node] = max(ssh,[],2);
    max_max_ssh = max(max_per_node(longitude >= lon_min & longitude <= lon_max & latitude >= lat_min & latitude <= lat_max),[],'all');
    min_max_ssh = min(max_per_node(longitude >= lon_min & longitude <= lon_max & latitude >= lat_min & latitude <= lat_max),[],'all');
    
    % Make max SSH plot
    figure('Position', [100 100 1100 1100]);
    trisurf(element',longitude,latitude,max_per_node)
    shading interp
    view(2)
    colormap turbo    
    c = colorbar;
    try
    	clim([min_max_ssh max_max_ssh])
    catch
    	caxis([min_max_ssh max_max_ssh]) % r2021b and prior
    end
    hold on
    for j = 1:size(states,1)
        state = states(j,:);
        geoshow(state,'FaceColor','none','EdgeColor','w')
    end
    contour3(lon_rough,lat_rough,is_water + 50,'-k','LineWidth',1) % shoreline
    xlabel('Longitude [°E]')
    ylabel('Latitude [°N]') 
    c.Label.String = 'SSH [m]';
    title([strcat("Maximum Inundation from ",string(t(1))," to ",string(t(end))),strcat(scen_label," Scenario")])
    axis([lon_min,lon_max,lat_min,lat_max])
    daspect([onedeglat onedeglon 1])
    ax = gca;
    ax.Color = [0.7 0.7 0.7];
    ax.FontSize = 14;
    set(gcf,'InvertHardCopy','off'); % land color won't save to png without this

    % Save figure out the output directory
    saveas(gcf,outfile,'png')
end
