#!/usr/bin/env python3
# Contact: Josh Port (joshua_port@uri.edu)
# Requirements: python3, numpy, netCDF4, scipy
#
# Scales OWI ASCII winds based on local land roughness &
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
        self.__group_main_var_time      = self.__group_main.createVariable("time", "i4", "time", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["i4"])
        self.__group_main_var_time_unix = self.__group_main.createVariable("time_unix", "i8", "time", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["i4"])
        self.__group_main_var_lon       = self.__group_main.createVariable("lon", "f8", "longitude", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f8"])
        self.__group_main_var_lat       = self.__group_main.createVariable("lat", "f8", "latitude", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["f8"])
        self.__group_main_var_u10       = self.__group_main.createVariable("U10", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_v10       = self.__group_main.createVariable("V10", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                           complevel=2,fill_value=netCDF4.default_fillvals["f4"])

        # Add attributes to variables
        self.__base_date = datetime(1990, 1, 1, 0, 0, 0)
        self.__group_main_var_time.units = "minutes since 1990-01-01 00:00:00 Z"
        self.__group_main_var_time.axis = "T"
        self.__group_main_var_time.coordinates = "time"
        
        self.__base_date_unix = datetime(1970, 1, 1, 0, 0, 0)
        self.__group_main_var_time_unix.units = "seconds since 1970-01-01 00:00:00"
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

    def get(self, idx):
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
    
    
def roughness_adjust(wind_lon, wind_lat, u_vel, v_vel, u_or_v, z0_wr, z0_hr):
    from scipy import interpolate
    from numpy import log, sqrt, zeros
    from math import exp
    import water_z0
    # Adjust every z0_wr as if it's water; save to z0_wr_water
    k = 0.40
    z_obs = 10
    wind_mag = sqrt(u_vel**2 + v_vel**2)
    z0_wr_water = zeros((len(wind_mag), len(wind_mag[0])))
    for i in range(len(wind_mag)):
        for j in range(len(wind_mag[0])):
            if wind_mag[i,j] == 0: 
                continue # z0_wr_water is initialized to 0
            else:
                ust_est = water_z0.retrieve_ust_U10(wind_mag[i,j], z_obs)
                z0_wr_water[i,j] = z_obs * exp(-(k * wind_mag[i,j]) / ust_est) 
    # Interpolate z0_wr to wind resolution just in case their resolution differs
    z0_wr_interpolant = interpolate.interp2d(z0_wr.lon(), z0_wr.lat(), z0_wr.land_rough(), kind='linear')
    z0_wr_wr_grid = z0_wr_interpolant(wind_lon, wind_lat)
    del z0_wr_interpolant
    # Scale input wind up to z_ref before interpolating using equations 9 & 10 here: https://dr.lib.iastate.edu/handle/20.500.12876/1131
    z_ref = 80 # Per Isaac the logarithmic profile only applies in the near surface layer, which extends roughly 80m up; to verify with lit review
    b = 1 / (log(10) - log(z0_wr_wr_grid)) # Eq 10
    if u_or_v == 'u':
        wind_z_ref = u_vel * (1 + b * log(z_ref / 10)) # Eq 9
    elif u_or_v == 'v':
        wind_z_ref = v_vel * (1 + b * log(z_ref / 10)) # Eq 9
    # Interpolate wind_z_ref and z0_wr_water to z0_hr resolution
    wind_interpolant = interpolate.interp2d(wind_lon, wind_lat, wind_z_ref, kind='linear')
    wind_z_ref_hr_grid = wind_interpolant(z0_hr.lon(), z0_hr.lat())
    del wind_interpolant
    z0_water_interpolant = interpolate.interp2d(wind_lon, wind_lat, z0_wr_water, kind='linear')
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
    wind_adjust = wind_z_ref_hr_grid / (1 + b * log(z_ref / 10)) # Eq 9; roughness-adjusted wind speed
    return wind_adjust
    
def main():
    import argparse
    from datetime import datetime
    parser = argparse.ArgumentParser(description="Convert HBL output to alternate formats")

    # Arguments
    parser.add_argument("-o", metavar="outfile", type=str, help="Name of output file to be created", required=False, default="scaled_wind")
    parser.add_argument("-hr", metavar="highres_roughness", type=str, help="High-resolution land roughness file", required=True)
    parser.add_argument("-w", metavar="wind", type=str, help="Wind file to be scaled and subsetted; must be in OWI ASCII format", required=True)
    parser.add_argument("-wr", metavar="wind_roughness", type=str, help="Wind-resolution land roughness file", required=True)

    # Read the command line arguments
    args = parser.parse_args()

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

    z0_hr = Roughness(args.hr)
    z0_wr = Roughness(args.wr)

    time_index = 0
    while time_index < num_times:
        owi_ascii = OwiAsciiWind(args.w, time_index)
        print("INFO: Processing time slice {:d} of {:d}".format(time_index + 1, num_times), flush=True)
        wind_data = owi_ascii.get(time_index)
        if not wind:
            wind = NetcdfOutput(args.o, z0_hr.lon(), z0_hr.lat())
        uvel_scaled = roughness_adjust(wind_data.wind_grid().lon1d(), wind_data.wind_grid().lat1d(), wind_data.u_velocity(), wind_data.v_velocity(), 'u', z0_wr, z0_hr)
        vvel_scaled = roughness_adjust(wind_data.wind_grid().lon1d(), wind_data.wind_grid().lat1d(), wind_data.u_velocity(), wind_data.v_velocity(), 'v', z0_wr, z0_hr)
        wind.append(time_index, wind_data.date(), uvel_scaled, vvel_scaled)
        time_index += 1  
    
    wind.close()

if __name__ == '__main__':
    main()
