#!/usr/bin/env python3
# Contact: Josh Port (joshua_port@uri.edu)
# Requirements: python3, numpy, netCDF4, pyproj, scipy
#
# Scales OWI ASCII, WND, or blended OWI ASCII + WND winds based on local surface roughness
# Outputs a value at every grid point in the roughness file
#
class WindGrid:
    def __init__(self, lon, lat):
        import numpy
        self.__n_longitude = len(lon)
        self.__n_latitude = len(lat)
        self.__d_longitude = round(lon[1] - lon[0], 4)
        self.__d_latitude = round(lat[1] - lat[0], 4)
        self.__lon = numpy.empty([self.__n_latitude, self.__n_longitude], dtype=numpy.float64)
        self.__lat = numpy.empty([self.__n_latitude, self.__n_longitude], dtype=numpy.float64)
        lon = numpy.array(lon)
        lat = numpy.array(lat)
        lon = numpy.where(lon > 180, lon - 360, lon)
        self.__xll = min(lon)
        self.__yll = min(lat)
        self.__xur = max(lon)
        self.__yur = max(lat)
        self.__lon,self.__lat = numpy.meshgrid(lon,lat) #sparse=True is an avenue to explore for saving memory
        self.__lon1d = numpy.array(lon)
        self.__lat1d = numpy.array(lat)

    def lon(self):
        return self.__lon

    def lat(self):
        return self.__lat

    def lon1d(self):
        return self.__lon1d

    def lat1d(self):
        return self.__lat1d

    def d_longitude(self):
        return self.__d_longitude

    def d_latitude(self):
        return self.__d_latitude

    def n_longitude(self):
        return self.__n_longitude

    def n_latitude(self):
        return self.__n_latitude

    def xll(self):
        return self.__xll

    def yll(self):
        return self.__yll

    def xur(self):
        return self.__xur

    def yur(self):
        return self.__yur

    @staticmethod
    def generate_equidistant_grid(grid=None,xll=None,yll=None,xur=None,yur=None,dx=None,dy=None):
        if grid:
            return WindGrid.__generate_equidistant_grid_from_grid(grid)
        if xll and yll and xur and yur and dx and dy:
            return WindGrid.__generate_equidistant_grid_from_corners(xll,yll,xur,yur,dx,dy)
        raise RuntimeError("No valid function call provided")

    @staticmethod
    def __generate_equidistant_grid_from_grid(grid):
        import numpy as np
        x = np.arange(grid.xll(), grid.xur(), grid.d_longitude())
        y = np.arange(grid.yll(), grid.yur(), grid.d_latitude())
        return WindGrid(x,y)

    @staticmethod
    def __generate_equidistant_grid_from_corners(x1,y1,x2,y2,dx,dy):
        import numpy as np
        x = np.arange(x1,x2,dx)
        y = np.arange(y1,y2,dy)
        return WindGrid(x,y)

    @staticmethod
    def interpolate_to_grid(original_grid, original_data, new_grid):
        from scipy import interpolate
        func = interpolate.interp2d(original_grid.lon1d(),original_grid.lat1d(),original_data,kind='linear')
        return func(new_grid.lon1d(),new_grid.lat1d())


class WindData:
    def __init__(self, date, wind_grid, u_velocity, v_velocity):
        import numpy
        self.__u_velocity = numpy.array(u_velocity)
        self.__v_velocity = numpy.array(v_velocity)
        self.__date = date
        self.__wind_grid = wind_grid

    def date(self):
        return self.__date

    def wind_grid(self):
        return self.__wind_grid 

    def u_velocity(self):
        return self.__u_velocity

    def v_velocity(self):
        return self.__v_velocity

    
class Roughness:
    def __init__(self, filename):
        self.__filename = filename
        self.__lon = self.__get_lon()
        self.__lat = self.__get_lat()
        self.__land_rough = self.__get_land_rough()

    def lon(self):
        return self.__lon

    def lat(self):
        return self.__lat
    
    def land_rough(self):
        return self.__land_rough

    def __get_lon(self):
        from netCDF4 import Dataset
        import numpy
        f = Dataset(self.__filename, 'r')
        lon = f.variables["lon"][:] 
        f.close()
        return numpy.array(lon)
        
    def __get_lat(self):
        from netCDF4 import Dataset
        import numpy
        f = Dataset(self.__filename, 'r')
        lat = f.variables["lat"][:] 
        f.close()
        return numpy.array(lat)

    def __get_land_rough(self):
        from netCDF4 import Dataset
        import numpy
        f = Dataset(self.__filename, 'r')
        land_rough = f.variables["land_rough"][:][:]
        f.close() 
        return numpy.array(land_rough)
    
    
class NetcdfOutput:
    def __init__(self, filename, lon, lat):
        import netCDF4
        from datetime import datetime
        self.__filename = filename
        self.__lon = lon
        self.__lat = lat
        self.__nc = netCDF4.Dataset(self.__filename + ".nc", "w")
        self.__nc.group_order = "Main"
        self.__nc.source = "scale_and_subset.py"
        self.__nc.author = "Josh Port"
        self.__nc.contact = "joshua_port@uri.edu"

        # Create main group
        self.__group_main = self.__nc.createGroup("Main")
        self.__group_main.rank = 1

        # Create dimensions
        self.__group_main_dim_time = self.__group_main.createDimension("time", None)
        self.__group_main_dim_longitude = self.__group_main.createDimension("longitude", len(self.__lon))
        self.__group_main_dim_latitude = self.__group_main.createDimension("latitude", len(self.__lat))

        # Create variables (with compression)
        self.__group_main_var_time      = self.__group_main.createVariable("time", "f4", "time", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_time_unix = self.__group_main.createVariable("time_unix", "f8", "time", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f8"]) # int64 isn't supported in DAP2 
        self.__group_main_var_lon       = self.__group_main.createVariable("lon", "f8", "longitude", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f8"])
        self.__group_main_var_lat       = self.__group_main.createVariable("lat", "f8", "latitude", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f8"])
        self.__group_main_var_u10       = self.__group_main.createVariable("U10", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_v10       = self.__group_main.createVariable("V10", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_spd       = self.__group_main.createVariable("spd", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_dir       = self.__group_main.createVariable("dir", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])

        # Add attributes to variables
        self.__base_date = datetime(1990, 1, 1, 0, 0, 0)
        self.__group_main_var_time.units = "minutes since 1990-01-01 00:00:00 Z"
        self.__group_main_var_time.axis = "T"
        self.__group_main_var_time.coordinates = "time"
        
        self.__base_date_unix = datetime(1970, 1, 1, 0, 0, 0)
        self.__group_main_var_time_unix.units = "seconds since 1970-01-01 00:00:00 Z"
        self.__group_main_var_time_unix.axis = "T"
        self.__group_main_var_time_unix.coordinates = "time"

        self.__group_main_var_lon.coordinates = "lon"
        self.__group_main_var_lon.units = "degrees_east"
        self.__group_main_var_lon.standard_name = "longitude"
        self.__group_main_var_lon.axis = "x"

        self.__group_main_var_lat.coordinates = "lat"
        self.__group_main_var_lat.units = "degrees_north"
        self.__group_main_var_lat.standard_name = "latitude"
        self.__group_main_var_lat.axis = "y"

        self.__group_main_var_u10.units = "m s-1"
        self.__group_main_var_u10.coordinates = "time lat lon"

        self.__group_main_var_v10.units = "m s-1"
        self.__group_main_var_v10.coordinates = "time lat lon"
        
        self.__group_main_var_spd.units = "m s-1"
        self.__group_main_var_spd.coordinates = "time lat lon"
        
        self.__group_main_var_dir.units = "degrees (meteorological convention; direction coming from)"
        self.__group_main_var_dir.coordinates = "time lat lon"

        self.__group_main_var_lat[:] = self.__lat
        self.__group_main_var_lon[:] = self.__lon

    def append(self, idx, date, uvel, vvel):
        delta = (date - self.__base_date)
        minutes = round((delta.days * 86400 + delta.seconds) / 60)
        
        delta_unix = (date - self.__base_date_unix)
        seconds = round(delta_unix.days * 86400 + delta_unix.seconds)

        self.__group_main_var_time[idx] = minutes
        self.__group_main_var_time_unix[idx] = seconds
        self.__group_main_var_u10[idx, :, :] = uvel
        self.__group_main_var_v10[idx, :, :] = vvel
        self.__group_main_var_spd[idx, :, :] = speed_from_uv(uvel, vvel)
        self.__group_main_var_dir[idx, :, :] = direction_from_uv(uvel, vvel)

    def close(self):
        self.__nc.close()
    

class OwiAsciiWind:
    # NOTE: This class assumes the same number of grid points in each time slice.
    # The conversion will fail if this isn't the case.
    def __init__(self, win_filename, idx):
        self.__win_filename = win_filename
        self.__idx = idx
        self.__num_lats = self.__get_num_lats()
        self.__num_lons = self.__get_num_lons()
        self.__win_idx_header_row = self.__get_win_idx_header_row()
        self.__date = self.__get_date()
        self.__grid = self.__get_grid()

    def date(self):
        return self.__date

    def grid(self):
        return self.__grid
    
    def __get_num_lats(self):
        win_file = open(self.__win_filename, 'r')
        lines = win_file.readlines()
        num_lats = lines[1][5:9]
        win_file.close()
        return int(num_lats)
    
    def __get_num_lons(self):
        win_file = open(self.__win_filename, 'r')
        lines = win_file.readlines()
        num_lons = lines[1][15:19]
        win_file.close()
        return int(num_lons)    
            
    def __get_win_idx_header_row(self):
        from math import ceil
        return 1 + 2 * ceil((self.__num_lats * self.__num_lons) / 8) * self.__idx + self.__idx

    def __get_date(self):
        from datetime import datetime
        win_file = open(self.__win_filename, 'r')
        lines = win_file.readlines()
        date_str = lines[self.__win_idx_header_row][68:80]
        idx_date = datetime(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]), int(date_str[8:10]), int(date_str[10:12]))
        win_file.close()
        return idx_date
    
    def __get_grid(self):
        from numpy import linspace
        win_file = open(self.__win_filename, 'r')
        lines = win_file.readlines()
        lat_step = float(lines[self.__win_idx_header_row][31:37])
        lon_step = float(lines[self.__win_idx_header_row][22:28])
        sw_corner_lat = float(lines[self.__win_idx_header_row][43:51])
        sw_corner_lon = float(lines[self.__win_idx_header_row][57:65])
        lat = linspace(sw_corner_lat, sw_corner_lat + (self.__num_lats - 1) * lat_step, self.__num_lats)
        lon = linspace(sw_corner_lon, sw_corner_lon + (self.__num_lons - 1) * lon_step, self.__num_lons)
        win_file.close()
        return WindGrid(lon, lat)

    def get(self):
        from math import ceil, floor
        win_file = open(self.__win_filename, 'r')
        lines = win_file.readlines()
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = self.__win_idx_header_row + 1 + floor(i / 8)
            lon_idx = i % self.__num_lons
            lat_idx = floor(i / self.__num_lons)
            uvel[lat_idx][lon_idx] = float(lines[line_idx][low_idx:high_idx])
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = self.__win_idx_header_row + 1 + floor(i / 8) + ceil((self.__num_lats * self.__num_lons) / 8) 
            lon_idx = i % self.__num_lons
            lat_idx = floor(i / self.__num_lons)
            vvel[lat_idx][lon_idx] = float(lines[line_idx][low_idx:high_idx])  
        win_file.close()           
        return WindData(self.__date, self.__grid, uvel, vvel)
  
    
class WndWindInp:
    def __init__(self, wind_inp_filename):
        self.__wind_inp_filename = wind_inp_filename
        self.__start_time = self.__get_start_time()
        self.__time_step = self.__get_time_step()
        self.__num_times = self.__get_num_times()
        self.__spatial_res = self.__get_spatial_res()
        self.__s_lim = self.__get_s_lim()
        self.__n_lim = self.__get_n_lim()
        self.__w_lim = self.__get_w_lim()
        self.__e_lim = self.__get_e_lim()
        self.__num_lats = self.__get_num_lats()
        self.__num_lons = self.__get_num_lons()
    
    def start_time(self):
        return self.__start_time

    def time_step(self):
        return self.__time_step
    
    def num_times(self):
        return self.__num_times
    
    def spatial_res(self):
        return self.__spatial_res  

    def num_lons(self):
        return self.__num_lons

    def num_lats(self):
        return self.__num_lats
    
    def s_lim(self):
        return self.__s_lim

    def w_lim(self):
        return self.__w_lim
    
    def __get_start_time(self):
        from datetime import datetime
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        datepart = lines[2].split()
        start_time = datetime(int(datepart[0]), int(datepart[1]), int(datepart[2]), int(datepart[3]), int(datepart[4]), int(datepart[5]))
        wind_inp_file.close()
        return start_time
    
    def __get_time_step(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        time_step = lines[3]
        wind_inp_file.close()
        return float(time_step)
    
    def __get_num_times(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        num_times = lines[4]
        wind_inp_file.close()
        return int(num_times)
    
    def __get_spatial_res(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        spatial_res = 1 / int(lines[7].strip().replace(".", ""))
        wind_inp_file.close()
        return float(spatial_res)
    
    def __get_s_lim(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        lat_bounds = lines[6].split()
        s_lim = lat_bounds[0]
        wind_inp_file.close()
        return float(s_lim)
    
    def __get_n_lim(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        lat_bounds = lines[6].split()
        n_lim = lat_bounds[1]
        wind_inp_file.close()
        return float(n_lim)

    def __get_w_lim(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        lat_bounds = lines[5].split()
        w_lim = lat_bounds[0]
        wind_inp_file.close()
        return float(w_lim)

    def __get_e_lim(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        lat_bounds = lines[5].split()
        e_lim = lat_bounds[1]
        wind_inp_file.close()
        return float(e_lim)
    
    def __get_num_lats(self):
        num_lats = (self.__n_lim - self.__s_lim) / self.__spatial_res + 1
        return int(num_lats)
    
    def __get_num_lons(self):
        num_lons = (self.__e_lim - self.__w_lim) / self.__spatial_res + 1
        return int(num_lons)


class WndWind:
    def __init__(self, wnd_filename, wind_inp, idx):
        self.__wnd_filename = wnd_filename
        self.__wind_inp = wind_inp
        self.__idx = idx
        self.__num_lats = self.__wind_inp.num_lats()
        self.__num_lons = self.__wind_inp.num_lons()
        self.__sw_corner_lat = self.__wind_inp.s_lim()
        self.__sw_corner_lon = self.__wind_inp.w_lim()
        self.__lat_step = self.__wind_inp.spatial_res()
        self.__lon_step = self.__wind_inp.spatial_res()
        self.__idx_start_row = self.__get_idx_start_row()
        self.__date = self.__get_date()
        self.__grid = self.__get_grid()

    def date(self):
        return self.__date

    def grid(self):
        return self.__grid 
            
    def __get_idx_start_row(self):
        return self.__num_lats * self.__num_lons * self.__idx

    def __get_date(self):
        from datetime import timedelta
        return self.__wind_inp.start_time() + timedelta(hours=self.__idx * self.__wind_inp.time_step())
    
    def __get_grid(self):
        from numpy import linspace
        lat = linspace(self.__sw_corner_lat, self.__sw_corner_lat + (self.__num_lats - 1) * self.__lat_step, self.__num_lats)
        lon = linspace(self.__sw_corner_lon, self.__sw_corner_lon + (self.__num_lons - 1) * self.__lon_step, self.__num_lons)
        return WindGrid(lon, lat)

    def get(self):
        from math import floor
        wnd_file = open(self.__wnd_filename, 'r')
        lines = wnd_file.readlines()
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            line_idx = self.__idx_start_row + i
            lon_idx = i % self.__num_lons
            lat_idx = self.__num_lats - floor(i / self.__num_lons) - 1 # WND starts in the NW corner and goes row by row
            uvel[lat_idx][lon_idx] = float(lines[line_idx][0:9])   
            vvel[lat_idx][lon_idx] = float(lines[line_idx][10:19])   
        wnd_file.close()
        return WindData(self.__date, self.__grid, uvel, vvel)
    
    
def direction_from_uv(u_vel, v_vel):
    from numpy import arctan, pi, rad2deg, where
    u_vel[where(u_vel == 0)] = 0.0000000001 # imperceptibly hurt precision to avoid divide by zero errors
    dir_math = arctan(v_vel / u_vel)
    dir_math[where(u_vel < 0)] = dir_math[where(u_vel < 0)] + pi; # arctan only returns values from -pi to pi. We need values from 0 to 2*pi.
    dir_met_radians = ((3 * pi / 2) - dir_math) % (2 * pi) # Meteorological heading
    return rad2deg(dir_met_radians)


def speed_from_uv(u_vel, v_vel):
    from numpy import sqrt
    return sqrt(u_vel**2 + v_vel**2)

    
def roughness_adjust(back_wind, param_wind, wfmt, z0_wr, z0_hr, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0):
    from scipy import interpolate
    from numpy import exp, log, where, zeros
    import water_z0
    k = 0.40
    z_obs = 10
    z0_param = 0.0033
    almost_zero = 0.000001
    # Scale input wind up to z_ref using equations 9 & 10 here: https://dr.lib.iastate.edu/handle/20.500.12876/1131
    z_ref = 80 # Per Isaac the logarithmic profile only applies in the near surface layer, which extends roughly 80m up; to verify with lit review
    if (wfmt == "owi-ascii") | (wfmt == "blend"):
        # Interpolate wind to z0_wr resolution just in case their resolution differs
        z0_wr_interpolant = interpolate.interp2d(z0_wr.lon(), z0_wr.lat(), z0_wr.land_rough(), kind='linear')
        z0_wr_wr_grid_back = z0_wr_interpolant(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d())
        del z0_wr_interpolant
        # Scale to z_ref
        b = 1 / (log(10) - log(z0_wr_wr_grid_back)) # Eq 10
        u_back_z_ref = back_wind.u_velocity() * (1 + b * log(z_ref / 10)) # Eq 9
        v_back_z_ref = back_wind.v_velocity() * (1 + b * log(z_ref / 10)) # Eq 9
    if (wfmt == "wnd") | (wfmt == "blend"):
        # Wnd winds are marine exposure; assume z0 = 0.0033 at every point to be consistent with Deb's logic; see 8/10/22 email from Deb
        z0_wr_wr_grid_param = zeros((len(param_wind.u_velocity()), len(param_wind.u_velocity()[0]))) + z0_param
        # Scale to z_ref
        b = 1 / (log(10) - log(z0_wr_wr_grid_param)) # Eq 10
        u_param_z_ref = param_wind.u_velocity() * (1 + b * log(z_ref / 10)) # Eq 9
        v_param_z_ref = param_wind.v_velocity() * (1 + b * log(z_ref / 10)) # Eq 9
    # Define wind; including blending if necessary
    if wfmt == "owi-ascii":
        wind_z_ref = WindData(back_wind.date(), back_wind.wind_grid(), u_back_z_ref, v_back_z_ref)
    elif wfmt == "wnd":
        wind_z_ref = WindData(param_wind.date(), param_wind.wind_grid(), u_param_z_ref, v_param_z_ref)
    elif wfmt == "blend":
        back_wind_z_ref = WindData(back_wind.date(), back_wind.wind_grid(), u_back_z_ref, v_back_z_ref)        
        param_wind_z_ref = WindData(param_wind.date(), param_wind.wind_grid(), u_param_z_ref, v_param_z_ref)
        wind_z_ref = blend(back_wind_z_ref, param_wind_z_ref, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0)    
    # Adjust every z0_wr as if it's water; save to z0_wr_water
    wind_mag = speed_from_uv(wind_z_ref.u_velocity(), wind_z_ref.v_velocity())
    wind_mag[where(wind_mag == 0)] = almost_zero # wind_mag == 0 would cause a divide by zero error below
    ust_est = water_z0.retrieve_ust_U10(wind_mag, z_obs) 
    z0_wr_water = z_obs * exp(-(k * wind_mag) / ust_est)   
    # Interpolate wind_z_ref and z0_wr_water to z0_hr resolution
    u_interpolant = interpolate.interp2d(wind_z_ref.wind_grid().lon1d(), wind_z_ref.wind_grid().lat1d(), wind_z_ref.u_velocity(), kind='linear')
    u_z_ref_hr_grid = u_interpolant(z0_hr.lon(), z0_hr.lat())
    v_interpolant = interpolate.interp2d(wind_z_ref.wind_grid().lon1d(), wind_z_ref.wind_grid().lat1d(), wind_z_ref.v_velocity(), kind='linear')
    v_z_ref_hr_grid = v_interpolant(z0_hr.lon(), z0_hr.lat())
    del u_interpolant, v_interpolant
    z0_water_interpolant = interpolate.interp2d(wind_z_ref.wind_grid().lon1d(), wind_z_ref.wind_grid().lat1d(), z0_wr_water, kind='linear')
    z0_wr_water_hr_grid = z0_water_interpolant(z0_hr.lon(), z0_hr.lat())
    del z0_water_interpolant
    # Re-assign roughness values over sea for z0_hr
    z0_hr_hr_grid = z0_hr.land_rough()
    for i in range(len(z0_hr_hr_grid)):
        for j in range(len(z0_hr_hr_grid[0])):
            if z0_hr_hr_grid[i,j] < 0.0031: # == 0.003, but floats are evil and round() is slow
                z0_hr_hr_grid[i,j] = z0_wr_water_hr_grid[i,j]
    # Scale back down to 10 meters using the local z0 value
    b = 1 / (log(10) - log(z0_hr_hr_grid)) # Eq 10
    u_adjust = u_z_ref_hr_grid / (1 + b * log(z_ref / 10)) # Eq 9; roughness-adjusted wind speed 
    v_adjust = v_z_ref_hr_grid / (1 + b * log(z_ref / 10)) # Eq 9; roughness-adjusted wind speed 
    return WindData(wind_z_ref.date(), WindGrid(z0_hr.lon(), z0_hr.lat()), u_adjust, v_adjust)


def generate_rmw_interpolant():
    from datetime import datetime
    from numpy import zeros
    from pandas import read_csv
    from scipy import interpolate
    TrackRMW = read_csv('TrackRMW.txt', header=0, delim_whitespace=True)
    TrackRMW_rows = len(TrackRMW)
    rmw = zeros((TrackRMW_rows,1))
    time_rmw = zeros((TrackRMW_rows,1))
    for i in range(0,TrackRMW_rows):
        rmw[i] = float(TrackRMW.iloc[i,8])
        time_rmw_date = datetime(TrackRMW.iloc[i,0], TrackRMW.iloc[i,1], TrackRMW.iloc[i,2], TrackRMW.iloc[i,3], TrackRMW.iloc[i,4], TrackRMW.iloc[i,5])
        if i == 0:
            time_rmw_date_0 = time_rmw_date
        time_rmw[i] = (time_rmw_date - time_rmw_date_0).total_seconds()
    rmw_interpolant = interpolate.interp1d(time_rmw.flatten(), rmw.flatten(), kind='linear')
    return rmw_interpolant, time_rmw_date_0


def generate_ctr_interpolant():
    from datetime import datetime
    from numpy import zeros
    from pandas import read_csv
    from scipy import interpolate
    fort22 = read_csv('fort.22', header=None)
    fort22_rows = len(fort22)
    lat_ctr = zeros((fort22_rows,1))
    lon_ctr = zeros((fort22_rows,1))
    time_ctr = zeros((fort22_rows,1))
    for i in range(0,fort22_rows):
        lat_ctr[i] = float(fort22.iloc[i,6].replace('N',''))/10 # Assumes northern hemisphere
        lon_ctr[i] = -float(fort22.iloc[i,7].replace('W',''))/10 # Assumes western hemisphere
        time_ctr_date = datetime.strptime(str(fort22.iloc[i,2]), '%Y%m%d%H')
        if i == 0:
            time_ctr_date_0 = time_ctr_date
        time_ctr[i] = (time_ctr_date - time_ctr_date_0).total_seconds()
    lon_ctr_interpolant = interpolate.interp1d(time_ctr.flatten(), lon_ctr.flatten(), kind='linear')
    lat_ctr_interpolant = interpolate.interp1d(time_ctr.flatten(), lat_ctr.flatten(), kind='linear')
    return lon_ctr_interpolant, lat_ctr_interpolant, time_ctr_date_0


def blend(back_wind, param_wind, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0):
    from numpy import zeros
    from pyproj import Geod
    from scipy import interpolate
    # Interpolate back_wind to the param_wind spatial resolution (temporal is assumed to be the same)
    u_interpolant = interpolate.interp2d(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d(), back_wind.u_velocity(), kind='linear')
    back_wind_u_interp = u_interpolant(param_wind.wind_grid().lon1d(), param_wind.wind_grid().lat1d())
    v_interpolant = interpolate.interp2d(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d(), back_wind.v_velocity(), kind='linear')
    back_wind_v_interp = v_interpolant(param_wind.wind_grid().lon1d(), param_wind.wind_grid().lat1d())
    # Determine storm center location at param_wind.date()
    int_param_wind_date = (param_wind.date() - time_ctr_date_0).total_seconds()
    lon_ctr_interp = lon_ctr_interpolant(int_param_wind_date)
    lat_ctr_interp = lat_ctr_interpolant(int_param_wind_date)
    # Determine RMW at param_wind.date()
    int_param_wind_date = (param_wind.date() - time_rmw_date_0).total_seconds()
    rmw_interp = rmw_interpolant(int_param_wind_date)
    # Blend outside RMW region and within low and high limits for wind speed, and apply background wind to vortex center
    low_pct_of_max = .667
    high_pct_of_max = .733
    mag_param = speed_from_uv(param_wind.u_velocity(), param_wind.v_velocity())
    max_wind = mag_param.max()
    low_lim = min(low_pct_of_max * max_wind, 15.5)
    high_lim = min(high_pct_of_max * max_wind, 20.5)
    lon_ctr_interp_grid = zeros((param_wind.wind_grid().lon1d().size, param_wind.wind_grid().lat1d().size)) + lon_ctr_interp
    lat_ctr_interp_grid = zeros((param_wind.wind_grid().lon1d().size, param_wind.wind_grid().lat1d().size)) + lat_ctr_interp
    wgs84_geod = Geod(ellps='WGS84') 
    _,_,dist_from_ctr = wgs84_geod.inv(lon_ctr_interp_grid, lat_ctr_interp_grid, param_wind.wind_grid().lon(), param_wind.wind_grid().lat())
    rmw_mask = dist_from_ctr <= rmw_interp # Make sure we don't blend within the RMW
    blend_mask = (low_lim < mag_param) & (mag_param < high_lim) & ~rmw_mask 
    back_mask = (mag_param <= low_lim) & ~rmw_mask
    u_blend = param_wind.u_velocity()
    v_blend = param_wind.v_velocity()
    alpha = (mag_param - low_lim) / (high_lim - low_lim)
    u_blend[blend_mask] = (alpha[blend_mask] * param_wind.u_velocity()[blend_mask]) + ((1 - alpha[blend_mask]) * back_wind_u_interp[blend_mask])
    v_blend[blend_mask] = (alpha[blend_mask] * param_wind.v_velocity()[blend_mask]) + ((1 - alpha[blend_mask]) * back_wind_v_interp[blend_mask])
    u_blend[back_mask] = back_wind_u_interp[back_mask]
    v_blend[back_mask] = back_wind_v_interp[back_mask]
    return WindData(param_wind.date(), param_wind.wind_grid(), u_blend, v_blend)

    
def main():
    import argparse
    from datetime import datetime
    
    start = datetime.now()

    # Build parser
    parser = argparse.ArgumentParser(description="Scale and subset input wind data based on high-resolution land roughness")
    parser.add_argument("-o", metavar="outfile", type=str, help="Name of output file to be created", required=False, default="scaled_wind")
    parser.add_argument("-hr", metavar="highres_roughness", type=str, help="High-resolution land roughness file", required=True)
    parser.add_argument("-w", metavar="wind", type=str, help="Wind file to be scaled and subsetted", required=True)
    parser.add_argument("-wback", metavar="wind_background", type=str, help="Background wind to be blended with the wind file; required if wfmt is blend", required=False)
    parser.add_argument("-wfmt", metavar="wind_format", type=str, help="Format of the input wind file. Supported values: owi-ascii, wnd, blend", required=True)
    parser.add_argument("-winp", metavar="wind_inp", type=str, help="Wind_Inp.txt metadata file; required if wfmt is wnd or blend", required=False)
    parser.add_argument("-wr", metavar="wind_roughness", type=str, help="Wind-resolution land roughness file; required if wfmt is owi-ascii or blend", required=False)

    # Read the command line arguments
    args = parser.parse_args()
    
    # Read relevant data & metadata
    wfmt = args.wfmt
    if wfmt == "owi-ascii":
        wind = None
        wind_file = open(args.w, 'r')
        lines = wind_file.readlines()
        num_dt = 0
        for i, line in enumerate(lines):
            if i == 0:
                start_date = datetime.strptime(line[55:65], '%Y%m%d%H')
                end_date = datetime.strptime(line[70:80], '%Y%m%d%H')
            elif line[65:67] == 'DT' and num_dt == 0:
                dt_1 = datetime.strptime(line[68:80], '%Y%m%d%H%M')
                num_dt += 1
            elif line[65:67] == 'DT' and num_dt == 1:
                dt_2 = datetime.strptime(line[68:80], '%Y%m%d%H%M')
                wind_file.close()
                break
        time_step = dt_2 - dt_1
        num_times = int((end_date - start_date) / time_step + 1)
        z0_wr = Roughness(args.wr)
    elif wfmt == "wnd":
        metadata = WndWindInp(args.winp)
        num_times = metadata.num_times()
    elif wfmt == "blend":
        metadata = WndWindInp(args.winp)
        num_times = metadata.num_times()
        z0_wr = Roughness(args.wr)
        # Generate interpolants used for every time slice
        lon_ctr_interpolant, lat_ctr_interpolant, time_ctr_date_0 = generate_ctr_interpolant()
        rmw_interpolant, time_rmw_date_0 = generate_rmw_interpolant()
    else:
        print("ERROR: Unsupported wind format. Please try again.")
        return
    z0_hr = Roughness(args.hr) 
    
    wind = None
    time_index = 0
    while time_index < num_times:
        print("INFO: Processing time slice {:d} of {:d}".format(time_index + 1, num_times), flush=True)
        if wfmt == "owi-ascii":
            owi_ascii = OwiAsciiWind(args.w, time_index)
            back_wind = owi_ascii.get()
            wind_scaled = roughness_adjust(back_wind, None, wfmt, z0_wr, z0_hr)
        elif wfmt == "wnd":
            wnd = WndWind(args.w, metadata, time_index)
            param_wind = wnd.get()
            wind_scaled = roughness_adjust(None, param_wind, wfmt, None, z0_hr)
        elif wfmt == "blend": 
            # Assumes the owi_ascii and wnd files have the same temporal resolution
            owi_ascii = OwiAsciiWind(args.wback, time_index)
            wnd = WndWind(args.w, metadata, time_index)
            back_wind = owi_ascii.get()
            param_wind = wnd.get()
            wind_scaled = roughness_adjust(back_wind, param_wind, wfmt, z0_wr, z0_hr, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0)
        if not wind:
            wind = NetcdfOutput(args.o, z0_hr.lon(), z0_hr.lat())
        wind.append(time_index, wind_scaled.date(), wind_scaled.u_velocity(), wind_scaled.v_velocity())
        time_index += 1  
    
    wind.close()
    print("RICHAMP wind generation complete. Runtime:",str(datetime.now() - start))

if __name__ == '__main__':
    main()
