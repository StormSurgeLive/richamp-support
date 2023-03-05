#!/usr/bin/env python3
# Contact: Josh Port (joshua_port@uri.edu)
#
# Scales OWI ASCII, WND, or blended OWI ASCII + WND winds based on local surface roughness
# Outputs a value at every grid point in the roughness file
#
import argparse
import datetime
import math
import multiprocessing
import netCDF4
import numpy
import pandas
import pyproj
import scipy.interpolate
import threading


class WindGrid:
    def __init__(self, lon, lat):
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
        self.__lon, self.__lat = numpy.meshgrid(lon, lat)  # sparse=True is an avenue to explore for saving memory
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
    def generate_equidistant_grid(grid=None, xll=None, yll=None, xur=None, yur=None, dx=None, dy=None):
        if grid:
            return WindGrid.__generate_equidistant_grid_from_grid(grid)
        if xll and yll and xur and yur and dx and dy:
            return WindGrid.__generate_equidistant_grid_from_corners(xll, yll, xur, yur, dx, dy)
        raise RuntimeError("No valid function call provided")

    @staticmethod
    def __generate_equidistant_grid_from_grid(grid):
        x = numpy.arange(grid.xll(), grid.xur(), grid.d_longitude())
        y = numpy.arange(grid.yll(), grid.yur(), grid.d_latitude())
        return WindGrid(x, y)

    @staticmethod
    def __generate_equidistant_grid_from_corners(x1, y1, x2, y2, dx, dy):
        x = numpy.arange(x1, x2, dx)
        y = numpy.arange(y1, y2, dy)
        return WindGrid(x, y)

    @staticmethod
    def interpolate_to_grid(original_grid, original_data, new_grid):
        func = scipy.interpolate.interp2d(original_grid.lon1d(), original_grid.lat1d(), original_data, kind='linear')
        return func(new_grid.lon1d(), new_grid.lat1d())


class WindData:
    def __init__(self, date, wind_grid, u_velocity, v_velocity):
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
    def __init__(self, filename, lat, land_rough):
        self.__filename = filename
        self.__lon = self.__get_lon()  # Subdomains always have full rows, so __lon can be initialized directly from the file
        self.__lat = lat  # lat and land_rough can be subset in subdomains, and if they were set like __lon they couldn't be manually updated without generating a file
        self.__land_rough = land_rough

    def filename(self):
        return self.__filename

    def lon(self):
        return self.__lon

    def lat(self):
        return self.__lat

    def land_rough(self):
        return self.__land_rough

    def __get_lon(self):
        f = netCDF4.Dataset(self.__filename, 'r')
        lon = f.variables["lon"][:]
        f.close()
        return numpy.array(lon)

    def get_lat_and_land_rough(filename):
        f = netCDF4.Dataset(filename, 'r')
        lat = numpy.array(f.variables["lat"][:])
        land_rough = numpy.array(f.variables["land_rough"][:][:])
        f.close()
        return lat, land_rough


class NetcdfOutput:
    def __init__(self, filename, lon, lat):
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
        self.__group_main_var_time = self.__group_main.createVariable("time", "f4", "time", zlib=True, complevel=2,
                                                                      fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_time_unix = self.__group_main.createVariable("time_unix", "i8", "time", zlib=True, complevel=2,
                                                                           fill_value=netCDF4.default_fillvals["i8"])  # int64 isn't supported in DAP2; still using unless RICHAMP needs DAP2
        self.__group_main_var_lon = self.__group_main.createVariable("lon", "f8", "longitude", zlib=True, complevel=2,
                                                                     fill_value=netCDF4.default_fillvals["f8"])
        self.__group_main_var_lat = self.__group_main.createVariable("lat", "f8", "latitude", zlib=True, complevel=2,
                                                                     fill_value=netCDF4.default_fillvals["f8"])
        # self.__group_main_var_u10       = self.__group_main.createVariable("U10", "f4", ("time", "latitude", "longitude"), zlib=True,
        #                                                                     complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        # self.__group_main_var_v10       = self.__group_main.createVariable("V10", "f4", ("time", "latitude", "longitude"), zlib=True,
        #                                                                     complevel=2,fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_spd = self.__group_main.createVariable("spd", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                     complevel=2, fill_value=netCDF4.default_fillvals["f4"])
        self.__group_main_var_dir = self.__group_main.createVariable("dir", "f4", ("time", "latitude", "longitude"), zlib=True,
                                                                     complevel=2, fill_value=netCDF4.default_fillvals["f4"])

        # Add attributes to variables
        self.__base_date = datetime.datetime(1990, 1, 1, 0, 0, 0)
        self.__group_main_var_time.units = "minutes since 1990-01-01 00:00:00 Z"
        self.__group_main_var_time.axis = "T"
        self.__group_main_var_time.coordinates = "time"

        self.__base_date_unix = datetime.datetime(1970, 1, 1, 0, 0, 0)
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

        # self.__group_main_var_u10.units = "m s-1"
        # self.__group_main_var_u10.coordinates = "time lat lon"

        # self.__group_main_var_v10.units = "m s-1"
        # self.__group_main_var_v10.coordinates = "time lat lon"

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
        # self.__group_main_var_u10[idx, :, :] = uvel
        # self.__group_main_var_v10[idx, :, :] = vvel
        self.__group_main_var_spd[idx, :, :] = magnitude_from_uv(uvel, vvel)
        self.__group_main_var_dir[idx, :, :] = dir_met_to_and_from_math(direction_from_uv(uvel, vvel))

    def close(self):
        self.__nc.close()


class OwiAsciiWind:
    def __init__(self, lines, idx):
        self.__lines = lines
        self.__idx = idx
        self.__num_lats, self.__num_lons, self.__win_idx_header_row, self.__date, self.__grid = self.__get_file_metadata()

    def date(self):
        return self.__date

    def grid(self):
        return self.__grid

    def __get_file_metadata(self):
        num_lats = int(self.__lines[1][5:9])
        num_lons = int(self.__lines[1][15:19])
        win_idx_header_row = 1 + 2 * math.ceil((num_lats * num_lons) / 8) * self.__idx + self.__idx
        date_str = self.__lines[win_idx_header_row][68:80]
        idx_date = datetime.datetime(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]), int(date_str[8:10]), int(date_str[10:12]))
        lat_step = float(self.__lines[win_idx_header_row][31:37])
        lon_step = float(self.__lines[win_idx_header_row][22:28])
        sw_corner_lat = float(self.__lines[win_idx_header_row][43:51])
        sw_corner_lon = float(self.__lines[win_idx_header_row][57:65])
        lat = numpy.linspace(sw_corner_lat, sw_corner_lat + (num_lats - 1) * lat_step, num_lats)
        lon = numpy.linspace(sw_corner_lon, sw_corner_lon + (num_lons - 1) * lon_step, num_lons)
        return num_lats, num_lons, win_idx_header_row, idx_date, WindGrid(lon, lat)

    def get(self):
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = self.__win_idx_header_row + 1 + math.floor(i / 8)
            lon_idx = i % self.__num_lons
            lat_idx = math.floor(i / self.__num_lons)
            uvel[lat_idx][lon_idx] = float(self.__lines[line_idx][low_idx:high_idx])
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = self.__win_idx_header_row + 1 + math.floor(i / 8) + math.ceil((self.__num_lats * self.__num_lons) / 8)
            lon_idx = i % self.__num_lons
            lat_idx = math.floor(i / self.__num_lons)
            vvel[lat_idx][lon_idx] = float(self.__lines[line_idx][low_idx:high_idx])
        return WindData(self.__date, self.__grid, uvel, vvel)


class WndWindInp:
    def __init__(self, wind_inp_filename):
        self.__wind_inp_filename = wind_inp_filename
        self.__start_time, self.__time_step, self.__num_times, self.__spatial_res, self.__s_lim, self.__n_lim, \
            self.__w_lim, self.__e_lim, self.__num_lats, self.__num_lons = self.__get_file_metadata()

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

    def __get_file_metadata(self):
        wind_inp_file = open(self.__wind_inp_filename, 'r')
        lines = wind_inp_file.readlines()
        datepart = lines[2].split()
        start_time = datetime.datetime(int(datepart[0]), int(datepart[1]), int(datepart[2]), int(datepart[3]), int(datepart[4]), int(datepart[5]))
        time_step = float(lines[3])
        num_times = int(lines[4])
        spatial_res = float(1 / int(lines[7].strip().replace(".", "")))
        lat_bounds = lines[6].split()
        lon_bounds = lines[5].split()
        s_lim = float(lat_bounds[0])
        n_lim = float(lat_bounds[1])
        w_lim = float(lon_bounds[0])
        e_lim = float(lon_bounds[1])
        num_lats = int((n_lim - s_lim) / spatial_res + 1)
        num_lons = int((e_lim - w_lim) / spatial_res + 1)
        wind_inp_file.close()
        return start_time, time_step, num_times, spatial_res, s_lim, n_lim, w_lim, e_lim, num_lats, num_lons


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
        self.__idlon_start_row = self.__get_idlon_start_row()
        self.__date = self.__get_date()
        self.__grid = self.__get_grid()

    def date(self):
        return self.__date

    def grid(self):
        return self.__grid

    def __get_idlon_start_row(self):
        return self.__num_lats * self.__num_lons * self.__idx

    def __get_date(self):
        return self.__wind_inp.start_time() + datetime.timedelta(hours=self.__idx * self.__wind_inp.time_step())

    def __get_grid(self):
        lat = numpy.linspace(self.__sw_corner_lat, self.__sw_corner_lat + (self.__num_lats - 1) * self.__lat_step, self.__num_lats)
        lon = numpy.linspace(self.__sw_corner_lon, self.__sw_corner_lon + (self.__num_lons - 1) * self.__lon_step, self.__num_lons)
        return WindGrid(lon, lat)

    def get(self):
        wnd_file = open(self.__wnd_filename, 'r')
        lines = wnd_file.readlines()
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            line_idx = self.__idlon_start_row + i
            lon_idx = i % self.__num_lons
            lat_idx = self.__num_lats - math.floor(i / self.__num_lons) - 1  # WND starts in the NW corner and goes row by row
            uvel[lat_idx][lon_idx] = float(lines[line_idx][0:9])
            vvel[lat_idx][lon_idx] = float(lines[line_idx][10:19])
        wnd_file.close()
        return WindData(self.__date, self.__grid, uvel, vvel)


def dir_met_to_and_from_math(direction):
    return (270 - direction) % 360  # Formula is the same each way


def direction_from_uv(u_vel, v_vel):
    u_vel[u_vel == 0] = 0.0000000001  # Avoid divide by zero errors
    dir_math = numpy.rad2deg(numpy.arctan(v_vel / u_vel))
    # arctan only returns values from -pi/2 to pi/2. We need values from 0 to 2*pi.
    dir_math[u_vel < 0] = dir_math[u_vel < 0] + 180  # Quadrants 2 & 3
    dir_math[dir_math < 0] = dir_math[dir_math < 0] + 360  # Quadrant 4
    return dir_math


def magnitude_from_uv(u_vel, v_vel):
    return numpy.sqrt(u_vel**2 + v_vel**2)


def angle_diff(deg1, deg2):
    delta = deg1 - deg2
    return abs((delta + 180) % 360 - 180)


def generate_directional_z0_interpolant(lon_grid, lat_grid, z0_hr_hr_grid, sigma, radius):
    # Generate a defined number of circular sectors ("cones") around each point in the RICHAMP grid
    # Use a Gaussian decay function to calculate a weighted z0 value for each cone based on the discrete z0 values within the cone
    # Use the same weighting function as John Ratcliff & Rick Luettich
    overall_mid_lat = (lat_grid[0, 0] + lat_grid[-1, 0]) / 2  # degrees N
    overall_mid_lon = (lon_grid[0, 0] + lon_grid[0, -1]) / 2  # degrees E
    cone_width = 30  # degrees
    half_cone_width = cone_width / 2
    cone_ctr_angle = numpy.linspace(0, 360, 13)
    wgs84_geod = pyproj.Geod(ellps='WGS84')
    _, _, approx_grid_resolution = wgs84_geod.inv(lon_grid[0, 0], lat_grid[0, 0], lon_grid[0, 0],
                                                  lat_grid[1, 0])  # assumes same resolution in lat and lon
    _, _, one_deg_lon = wgs84_geod.inv(overall_mid_lon - 0.5, overall_mid_lat, overall_mid_lon + 0.5, overall_mid_lat)
    _, _, one_deg_lat = wgs84_geod.inv(overall_mid_lon, overall_mid_lat - 0.5, overall_mid_lon, overall_mid_lat + 0.5)
    n_fwd_back = math.ceil(radius / approx_grid_resolution)
    n_lat = len(z0_hr_hr_grid)
    n_lon = len(z0_hr_hr_grid[0])
    n_z0 = len(cone_ctr_angle) - 1  # A row for 360 degrees exists to allow interpolation between 330 and 0, but we don't calculate z0 for it
    z0_directional = numpy.zeros((n_lat, n_lon, n_z0 + 1))
    # Pre-calculate distance and angle for points that could be in_cone
    mid_lon = math.ceil(n_lon / 2)
    mid_lat = math.ceil(n_lat / 2)
    lon_start = mid_lon - n_fwd_back
    lon_end = mid_lon + n_fwd_back + 1
    lat_start = mid_lat - n_fwd_back
    lat_end = mid_lat + n_fwd_back + 1
    full_end = 2 * n_fwd_back + 1
    _, _, distance = wgs84_geod.inv(numpy.zeros((full_end, full_end)) + lon_grid[mid_lat, mid_lon], numpy.zeros((full_end, full_end)) + lat_grid[mid_lat, mid_lon],
                                    lon_grid[lat_start:lat_end, lon_start:lon_end], lat_grid[lat_start:lat_end, lon_start:lon_end])
    weight = numpy.exp(-distance**2 / (2 * sigma**2))
    direction = direction_from_uv(one_deg_lon * (lon_grid[mid_lat, mid_lon] - lon_grid[lat_start:lat_end, lon_start:lon_end]),
                                  one_deg_lat * (lat_grid[mid_lat, mid_lon] - lat_grid[lat_start:lat_end, lon_start:lon_end]))
    in_cone_if_in_grid = numpy.zeros((full_end, full_end, n_z0), dtype=bool)
    full_cone_weight = numpy.zeros((n_z0))
    for k in range(n_z0):
        in_cone_if_in_grid[:, :, k] = numpy.logical_and(distance <= radius, angle_diff(direction, cone_ctr_angle[k]) <= half_cone_width)
        in_cone_if_in_grid[n_fwd_back, n_fwd_back, k] = True  # the point of interest must be in every cone
        full_cone_weight[k] = sum(weight[in_cone_if_in_grid[:, :, k]])
    # Calculate z0 for each cone at each point
    old_pct_complete = 0
    for i in range(n_lat):
        pct_complete = math.floor(100 * (i / n_lat))
        if pct_complete != old_pct_complete:
            print("INFO: Interpolant generation " + str(pct_complete) + "% complete", flush=True)
            old_pct_complete = pct_complete
        local_lat_start = max(0, n_fwd_back - i)
        local_lat_end = full_end - max(0, n_fwd_back + i + 1 - n_lat)
        lat_start = max(0, i - n_fwd_back)
        lat_end = min(n_lat, i + n_fwd_back + 1)
        for j in range(n_lon):
            local_lon_start = max(0, n_fwd_back - j)
            local_lon_end = full_end - max(0, n_fwd_back + j + 1 - n_lon)
            lon_start = max(0, j - n_fwd_back)
            lon_end = min(n_lon, j + n_fwd_back + 1)
            # Only recalculate weight sums near the edge of the domain (where some cones are cut off)
            if local_lon_start != 0 or local_lat_start != 0 or local_lon_end != full_end or local_lat_end != full_end:
                for k in range(n_z0):
                    z0_directional[i, j, k] = sum(weight[local_lat_start:local_lat_end, local_lon_start:local_lon_end][in_cone_if_in_grid[local_lat_start:local_lat_end, local_lon_start:local_lon_end, k]]
                                                  * z0_hr_hr_grid[lat_start:lat_end, lon_start:lon_end][in_cone_if_in_grid[local_lat_start:local_lat_end, local_lon_start:local_lon_end, k]]) \
                        / sum(weight[local_lat_start:local_lat_end, local_lon_start:local_lon_end][in_cone_if_in_grid[local_lat_start:local_lat_end, local_lon_start:local_lon_end, k]])
            else:  # Otherwise, use full_cone_weight
                for k in range(n_z0):
                    z0_directional[i, j, k] = sum(weight[in_cone_if_in_grid[:, :, k]] * z0_hr_hr_grid[lat_start:lat_end,
                                                  lon_start:lon_end][in_cone_if_in_grid[:, :, k]]) / full_cone_weight[k]
    z0_directional[:, :, n_z0] = z0_directional[:, :, 0]  # 360 degrees and 0 degrees are the same
    # Create interpolant
    z0_directional_interpolant = scipy.interpolate.RegularGridInterpolator(
        (lat_grid[:, 0], lon_grid[0, :], cone_ctr_angle), z0_directional, method='linear')
    print("INFO: Interpolant generation 100% complete", flush=True)
    return z0_directional_interpolant


def roughness_adjust(subd_inputs):
    # NOTE: Past versions of this function derived z0 from wind stress over water
    # That is not feasible performance-wise while also calculating directional z0, so that functionality has been removed
    # Constant z0 values directly from the appropriate roughness file are now used over water
    z0_param = 0.0033
    # Split out input parameters from subd_inputs
    back_wind = subd_inputs[0]
    param_wind = subd_inputs[1]
    wfmt = subd_inputs[2]
    z0_wr = subd_inputs[3]
    z0_hr = subd_inputs[4]
    z0_directional_interpolant = subd_inputs[5]
    lon_ctr_interpolant = subd_inputs[6]
    lat_ctr_interpolant = subd_inputs[7]
    rmw_interpolant = subd_inputs[8]
    time_ctr_date_0 = subd_inputs[9]
    time_rmw_date_0 = subd_inputs[10]
    # Scale input wind up to z_ref using equations 9 & 10 here: https://dr.lib.iastate.edu/handle/20.500.12876/1131
    z_ref = 80  # Per Isaac the logarithmic profile only applies in the near surface layer, which extends roughly 80m up; to verify with lit review
    if (wfmt == "owi-ascii") | (wfmt == "blend"):
        # Interpolate wind to z0_wr resolution just in case their resolution differs
        z0_wr_interpolant = scipy.interpolate.interp2d(z0_wr.lon(), z0_wr.lat(), z0_wr.land_rough(), kind='linear')
        z0_wr_wr_grid_back = z0_wr_interpolant(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d())
        del z0_wr_interpolant
        # Scale to z_ref
        b = 1 / (numpy.log(10) - numpy.log(z0_wr_wr_grid_back))  # Eq 10
        u_back_z_ref = back_wind.u_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
        v_back_z_ref = back_wind.v_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
    if (wfmt == "wnd") | (wfmt == "blend"):
        # Wnd winds are marine exposure; assume z0 = 0.0033 at every point to be consistent with Deb's logic; see 8/10/22 email from Deb
        z0_wr_wr_grid_param = numpy.zeros((len(param_wind.u_velocity()), len(param_wind.u_velocity()[0]))) + z0_param
        # Scale to z_ref
        b = 1 / (numpy.log(10) - numpy.log(z0_wr_wr_grid_param))  # Eq 10
        u_param_z_ref = param_wind.u_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
        v_param_z_ref = param_wind.v_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
    # Define wind; including blending if necessary
    if wfmt == "owi-ascii":
        wind_z_ref = WindData(back_wind.date(), back_wind.wind_grid(), u_back_z_ref, v_back_z_ref)
    elif wfmt == "wnd":
        wind_z_ref = WindData(param_wind.date(), param_wind.wind_grid(), u_param_z_ref, v_param_z_ref)
    elif wfmt == "blend":
        back_wind_z_ref = WindData(back_wind.date(), back_wind.wind_grid(), u_back_z_ref, v_back_z_ref)
        param_wind_z_ref = WindData(param_wind.date(), param_wind.wind_grid(), u_param_z_ref, v_param_z_ref)
        wind_z_ref = blend(back_wind_z_ref, param_wind_z_ref, lon_ctr_interpolant,
                           lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0)
    # Interpolate wind_z_ref to z0_hr resolution
    u_interpolant = scipy.interpolate.interp2d(wind_z_ref.wind_grid().lon1d(), wind_z_ref.wind_grid().lat1d(), wind_z_ref.u_velocity(), kind='linear')
    u_z_ref_hr_grid = u_interpolant(z0_hr.lon(), z0_hr.lat())
    v_interpolant = scipy.interpolate.interp2d(wind_z_ref.wind_grid().lon1d(), wind_z_ref.wind_grid().lat1d(), wind_z_ref.v_velocity(), kind='linear')
    v_z_ref_hr_grid = v_interpolant(z0_hr.lon(), z0_hr.lat())
    del u_interpolant, v_interpolant
    # Modify z0 based on directional roughness
    z0_hr_grid = WindGrid(z0_hr.lon(), z0_hr.lat())
    dir_hr_grid = direction_from_uv(u_z_ref_hr_grid, v_z_ref_hr_grid)
    z0_hr_directional = z0_directional_interpolant((z0_hr_grid.lat(), z0_hr_grid.lon(), dir_hr_grid))
    # Scale back down to 10 meters using the local z0 value
    b = 1 / (numpy.log(10) - numpy.log(z0_hr_directional))  # Eq 10
    u_adjust = u_z_ref_hr_grid / (1 + b * numpy.log(z_ref / 10))  # Eq 9; roughness-adjusted wind speed
    v_adjust = v_z_ref_hr_grid / (1 + b * numpy.log(z_ref / 10))  # Eq 9; roughness-adjusted wind speed
    return WindData(wind_z_ref.date(), z0_hr_grid, u_adjust, v_adjust)


def generate_rmw_interpolant():
    TrackRMW = pandas.read_csv('TrackRMW.txt', header=0, delim_whitespace=True)
    TrackRMW_rows = len(TrackRMW)
    rmw = numpy.zeros((TrackRMW_rows, 1))
    time_rmw = numpy.zeros((TrackRMW_rows, 1))
    for i in range(0, TrackRMW_rows):
        rmw[i] = float(TrackRMW.iloc[i, 8]) * 1000  # Convert from km to m
        time_rmw_date = datetime.datetime(TrackRMW.iloc[i, 0], TrackRMW.iloc[i, 1], TrackRMW.iloc[i, 2],
                                          TrackRMW.iloc[i, 3], TrackRMW.iloc[i, 4], TrackRMW.iloc[i, 5])
        if i == 0:
            time_rmw_date_0 = time_rmw_date
        time_rmw[i] = (time_rmw_date - time_rmw_date_0).total_seconds()
    rmw_interpolant = scipy.interpolate.interp1d(time_rmw.flatten(), rmw.flatten(), kind='linear')
    return rmw_interpolant, time_rmw_date_0


def generate_ctr_interpolant():
    fort22 = pandas.read_csv('fort.22', header=None)
    fort22_rows = len(fort22)
    lat_ctr = numpy.zeros((fort22_rows, 1))
    lon_ctr = numpy.zeros((fort22_rows, 1))
    time_ctr = numpy.zeros((fort22_rows, 1))
    for i in range(0, fort22_rows):
        lat_ctr[i] = float(fort22.iloc[i, 6].replace('N', ''))/10  # Assumes northern hemisphere
        lon_ctr[i] = -float(fort22.iloc[i, 7].replace('W', ''))/10  # Assumes western hemisphere
        time_ctr_date = datetime.datetime.strptime(str(fort22.iloc[i, 2]), '%Y%m%d%H')
        if i == 0:
            time_ctr_date_0 = time_ctr_date
        time_ctr[i] = (time_ctr_date - time_ctr_date_0).total_seconds()
    lon_ctr_interpolant = scipy.interpolate.interp1d(time_ctr.flatten(), lon_ctr.flatten(), kind='linear')
    lat_ctr_interpolant = scipy.interpolate.interp1d(time_ctr.flatten(), lat_ctr.flatten(), kind='linear')
    return lon_ctr_interpolant, lat_ctr_interpolant, time_ctr_date_0


def blend(back_wind, param_wind, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0):
    # Interpolate back_wind to the param_wind spatial resolution (temporal is assumed to be the same)
    u_interpolant = scipy.interpolate.interp2d(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d(), back_wind.u_velocity(), kind='linear')
    back_wind_u_interp = u_interpolant(param_wind.wind_grid().lon1d(), param_wind.wind_grid().lat1d())
    v_interpolant = scipy.interpolate.interp2d(back_wind.wind_grid().lon1d(), back_wind.wind_grid().lat1d(), back_wind.v_velocity(), kind='linear')
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
    mag_param = magnitude_from_uv(param_wind.u_velocity(), param_wind.v_velocity())
    max_wind = mag_param.max()
    low_lim = min(low_pct_of_max * max_wind, 15.5)
    high_lim = min(high_pct_of_max * max_wind, 20.5)
    lon_ctr_interp_grid = numpy.zeros((param_wind.wind_grid().lon1d().size, param_wind.wind_grid().lat1d().size)) + lon_ctr_interp
    lat_ctr_interp_grid = numpy.zeros((param_wind.wind_grid().lon1d().size, param_wind.wind_grid().lat1d().size)) + lat_ctr_interp
    wgs84_geod = pyproj.Geod(ellps='WGS84')
    _, _, dist_from_ctr = wgs84_geod.inv(lon_ctr_interp_grid, lat_ctr_interp_grid, param_wind.wind_grid().lon(), param_wind.wind_grid().lat())
    rmw_mask = dist_from_ctr <= rmw_interp  # Make sure we don't blend within the RMW
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


def subd_prep(z0_hr, z0_directional_interpolant, threads):
    # Define subdomain indices for multiprocessing; subdomains are comprised of full rows and they are as close to the same size as possible
    subd_rows = math.floor(z0_hr.lat().size / threads)
    subd_start_index = numpy.zeros([threads, 1], dtype=int)
    subd_end_index = numpy.zeros([threads, 1], dtype=int)
    for i in range(0, threads):
        subd_end_index[i] = subd_rows * (i + 1)
    for i in range(0, z0_hr.lat().size % threads):
        subd_end_index[threads - (i + 1)] = subd_end_index[threads - (i + 1)] + (z0_hr.lat().size % threads - i)
    for i in range(1, threads):
        subd_start_index[i] = subd_end_index[i - 1]
    # Calculate subdomain quantities that will be used for each time slice
    subd_z0_hr = [[] for i in range(threads)]
    subd_z0_directional_interpolant = [[] for i in range(threads)]
    for i in range(0, threads):
        subd_z0_hr[i] = Roughness(z0_hr.filename(), z0_hr.lat()[int(subd_start_index[i]):int(subd_end_index[i])],
                                  z0_hr.land_rough()[int(subd_start_index[i]):int(subd_end_index[i]), :])
        subd_z0_directional_interpolant[i] = scipy.interpolate.RegularGridInterpolator((z0_directional_interpolant.grid[0][int(subd_start_index[i]):int(subd_end_index[i])],
                                                                                        z0_directional_interpolant.grid[1][:], z0_directional_interpolant.grid[2][:]),
                                                                                       z0_directional_interpolant.values[int(subd_start_index[i]):int(subd_end_index[i]), :, :], method='linear')
    return subd_z0_hr, subd_z0_directional_interpolant, subd_start_index, subd_end_index


def subd_restitch_domain(subd_wind_scaled, subd_start_index, subd_end_index, hr_shape, threads):
    u_scaled = numpy.zeros(hr_shape)
    v_scaled = numpy.zeros(hr_shape)
    for i in range(0, threads):
        u_scaled[int(subd_start_index[i]):int(subd_end_index[i]), :] = subd_wind_scaled[i].u_velocity()
        v_scaled[int(subd_start_index[i]):int(subd_end_index[i]), :] = subd_wind_scaled[i].v_velocity()
    return u_scaled, v_scaled


def main():
    start = datetime.datetime.now()

    # Build parser
    parser = argparse.ArgumentParser(description="Scale and subset input wind data based on high-resolution land roughness")
    parser.add_argument("-hr", metavar="highres_roughness", type=str, help="High-resolution land roughness file", required=True)
    parser.add_argument("-o", metavar="outfile", type=str, help="Name of output file to be created", required=False, default="scaled_wind")
    parser.add_argument("-r", metavar="radius", type=int,
                        help="Sector radius for directional z0 calculation, in meters; will be ignored if z0sv is false", required=False, default=3000)
    parser.add_argument("-sigma", metavar="sigma", type=int,
                        help="Weighting parameter for directional z0 calculation, in meters; will be ignored if z0sv is false", required=False, default=1000)
    parser.add_argument("-t", metavar="threads", type=int,
                        help="Number of threads to use for calculations; must not exceed the number available; total threads = t + wasync", required=False, default=1)
    parser.add_argument("-w", metavar="wind", type=str, help="Wind file to be scaled and subsetted", required=True)
    parser.add_argument("-wasync", help="Add this flag to begin scaling winds for the next time step while writing the output for the current time step; "
                        + "writes are NOT thread safe, so only do this if roughness_adjust always takes longer than wind.append; total threads = t + wasync", action='store_true', required=False, default=False)
    parser.add_argument("-wback", metavar="wind_background", type=str,
                        help="Background wind to be blended with the wind file; required if wfmt is blend", required=False)
    parser.add_argument("-wfmt", metavar="wind_format", type=str,
                        help="Format of the input wind file. Supported values: owi-ascii, wnd, blend", required=True)
    parser.add_argument("-winp", metavar="wind_inp", type=str, help="Wind_Inp.txt metadata file; required if wfmt is wnd or blend", required=False)
    parser.add_argument("-wr", metavar="wind_roughness", type=str,
                        help="Wind-resolution land roughness file; required if wfmt is owi-ascii or blend", required=False)
    parser.add_argument("-z0sv", help="Add this flag to generate and save off a directional z0 interpolant; do this in advance to save time during regular runs",
                        action='store_true', required=False, default=False)
    parser.add_argument("-z0name", metavar="z0_name", type=str,
                        help="Name of directional z0 interpolant file; it will be generated if z0sv is True and loaded if z0sv is False", required=False, default='z0_interp')

    # Read the command line arguments
    args = parser.parse_args()

    # Read relevant data & metadata
    wfmt = args.wfmt
    if wfmt == "owi-ascii":
        win_file = open(args.w, 'r')
        lines = win_file.readlines()
        num_dt = 0
        for i, line in enumerate(lines):
            if i == 0:
                start_date = datetime.datetime.strptime(line[55:65], '%Y%m%d%H')
                end_date = datetime.datetime.strptime(line[70:80], '%Y%m%d%H')
            elif line[65:67] == 'DT' and num_dt == 0:
                dt_1 = datetime.datetime.strptime(line[68:80], '%Y%m%d%H%M')
                num_dt += 1
            elif line[65:67] == 'DT' and num_dt == 1:
                dt_2 = datetime.datetime.strptime(line[68:80], '%Y%m%d%H%M')
                break
        time_step = dt_2 - dt_1
        num_times = int((end_date - start_date) / time_step + 1)
        wr_lat, wr_land_rough = Roughness.get_lat_and_land_rough(args.wr)
        z0_wr = Roughness(args.wr, wr_lat, wr_land_rough)
    elif wfmt == "wnd":
        metadata = WndWindInp(args.winp)
        num_times = metadata.num_times()
    elif wfmt == "blend":
        win_file = open(args.wback, 'r')
        lines = win_file.readlines()
        metadata = WndWindInp(args.winp)
        num_times = metadata.num_times()
        wr_lat, wr_land_rough = Roughness.get_lat_and_land_rough(args.wr)
        z0_wr = Roughness(args.wr, wr_lat, wr_land_rough)
        # Generate blend-specific interpolants used for every time slice
        lon_ctr_interpolant, lat_ctr_interpolant, time_ctr_date_0 = generate_ctr_interpolant()
        rmw_interpolant, time_rmw_date_0 = generate_rmw_interpolant()
    else:
        print("ERROR: Unsupported wind format. Please try again.", flush=True)
        return
    # Done this way so lat and land_rough can be updated later; see class
    hr_lat, hr_land_rough = Roughness.get_lat_and_land_rough(args.hr)
    z0_hr = Roughness(args.hr, hr_lat, hr_land_rough)
    lon_grid, lat_grid = numpy.meshgrid(z0_hr.lon(), z0_hr.lat())

    # Generate or load directional z0 interpolants
    if args.z0sv:
        print("INFO: z0sv is True, so a directional z0 interpolant file will be generated. This will take a while.", flush=True)
        print("INFO: Generating directional z0 interpolant...", flush=True)
        z0_directional_interpolant = generate_directional_z0_interpolant(lon_grid, lat_grid, z0_hr.land_rough(), args.sigma, args.r)
        numpy.save(args.z0name + '.npy', z0_directional_interpolant)
    else:
        print("INFO: Loading directional z0 interpolant...", flush=True)
        z0_directional_interpolant = numpy.load(args.z0name + '.npy', allow_pickle=True)[()]

    # Define subdomains for multiprocessing
    subd_z0_hr, subd_z0_directional_interpolant, subd_start_index, subd_end_index = subd_prep(z0_hr, z0_directional_interpolant, args.t)

    # Scale wind one time slice at a time
    wind = None
    time_index = 0
    # The conditional results in a null context manager if writes are synchronous
    with multiprocessing.Pool(args.t) as pool:
        while time_index < num_times:
            print("INFO: Processing time slice {:d} of {:d}".format(time_index + 1, num_times), flush=True)
            subd_inputs = [[] for i in range(args.t)]
            # Generate inputs for roughness_adjust
            if wfmt == "owi-ascii":
                owi_ascii = OwiAsciiWind(lines, time_index)
                back_wind = owi_ascii.get()
                for i in range(0, args.t):
                    subd_inputs[i] = [back_wind, None, wfmt, z0_wr, subd_z0_hr[i], subd_z0_directional_interpolant[i], None, None, None, None, None]
            elif wfmt == "wnd":
                wnd = WndWind(args.w, metadata, time_index)
                param_wind = wnd.get()
                for i in range(0, args.t):
                    subd_inputs[i] = [None, param_wind, wfmt, None, subd_z0_hr[i], subd_z0_directional_interpolant[i], None, None, None, None, None]
            elif wfmt == "blend":
                # Assumes the owi_ascii and wnd files have the same temporal resolution
                owi_ascii = OwiAsciiWind(lines, time_index)
                wnd = WndWind(args.w, metadata, time_index)
                back_wind = owi_ascii.get()
                param_wind = wnd.get()
                for i in range(0, args.t):
                    subd_inputs[i] = [back_wind, param_wind, wfmt, z0_wr, subd_z0_hr[i], subd_z0_directional_interpolant[i],
                                      lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0]
            # Call roughness_adjust for all subdomains in parallel
            subd_wind_scaled = pool.map(roughness_adjust, subd_inputs)
            u_scaled, v_scaled = subd_restitch_domain(subd_wind_scaled, subd_start_index, subd_end_index, z0_hr.land_rough().shape, args.t)
            wind_scaled = WindData(subd_wind_scaled[0].date(), WindGrid(z0_hr.lon(), z0_hr.lat()), u_scaled, v_scaled)
            # Write to NetCDF; single-threaded with optional asynchronicity for now, as thread-safe NetCDF is complicated
            if not wind:
                wind = NetcdfOutput(args.o, z0_hr.lon(), z0_hr.lat())
            if args.wasync and num_times - time_index > 1:
                threading.Thread(target=wind.append, args=(time_index, wind_scaled.date(),
                                 wind_scaled.u_velocity(), wind_scaled.v_velocity())).start()
            else:
                wind.append(time_index, wind_scaled.date(), wind_scaled.u_velocity(), wind_scaled.v_velocity())
            time_index += 1

    if (wfmt == "owi-ascii") | (wfmt == "blend"):
        win_file.close()
    wind.close()
    print("RICHAMP wind generation complete. Runtime:", str(datetime.datetime.now() - start), flush=True)


if __name__ == '__main__':
    main()
