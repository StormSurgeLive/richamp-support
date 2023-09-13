#!/usr/bin/env python3
# Contact: Josh Port (joshua_port@uri.edu)
#
# Scales OWI ASCII, WND, or blended OWI ASCII + WND winds based on local surface roughness
# Outputs a value at every point in the high-res roughness file for each time slice in the input wind file
#
import argparse
import concurrent.futures
import datetime
import math
import netCDF4
import numpy
import pandas
import pickle
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
        func = scipy.interpolate.RectBivariateSpline(original_grid.lat1d(), original_grid.lon1d(), original_data, kx=1, ky=1)
        return func(new_grid.lat1d(), new_grid.lon1d())


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
    def __init__(self, lon, lat, land_rough):
        self.__lon = lon
        self.__lat = lat
        self.__land_rough = land_rough

    def lon(self):
        return self.__lon

    def lat(self):
        return self.__lat

    def land_rough(self):
        return self.__land_rough

    def get(filename):
        f = netCDF4.Dataset(filename, 'r')
        lon = numpy.array(f.variables["lon"][:])
        lat = numpy.array(f.variables["lat"][:])
        land_rough = numpy.array(f.variables["land_rough"][:][:])
        f.close()
        return lon, lat, land_rough


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

    def append(self, idx, date, uvel, vvel, lock):
        if lock:
            lock.acquire()

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

        if lock:
            lock.release()

    def close(self):
        self.__nc.close()


class OwiAsciiWind:
    def __init__(self, lines):
        self.__lines = lines
        self.__grid = self.__get_grid()
        self.__num_lats = self.__grid.n_latitude()
        self.__num_lons = self.__grid.n_longitude()

    def grid(self):
        return self.__grid

    def __get_grid(self):
        num_lats = int(self.__lines[1][5:9])
        num_lons = int(self.__lines[1][15:19])
        lat_step = float(self.__lines[1][31:37])
        lon_step = float(self.__lines[1][22:28])
        sw_corner_lat = float(self.__lines[1][43:51])
        sw_corner_lon = float(self.__lines[1][57:65])
        lat = numpy.linspace(sw_corner_lat, sw_corner_lat + (num_lats - 1) * lat_step, num_lats)
        lon = numpy.linspace(sw_corner_lon, sw_corner_lon + (num_lons - 1) * lon_step, num_lons)
        return WindGrid(lon, lat)

    def num_times(self):
        num_dt = 0
        for i, line in enumerate(self.__lines):
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
        return int((end_date - start_date) / time_step + 1)

    def get(self, idx):
        win_idx_header_row = 1 + 2 * math.ceil((self.__num_lats * self.__num_lons) / 8) * idx + idx
        date_str = self.__lines[win_idx_header_row][68:80]
        idx_date = datetime.datetime(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]), int(date_str[8:10]), int(date_str[10:12]))
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = win_idx_header_row + 1 + math.floor(i / 8)
            lon_idx = i % self.__num_lons
            lat_idx = math.floor(i / self.__num_lons)
            uvel[lat_idx][lon_idx] = float(self.__lines[line_idx][low_idx:high_idx])
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            low_idx = 1 + 10 * (i % 8)
            high_idx = 10 + 10 * (i % 8)
            line_idx = win_idx_header_row + 1 + math.floor(i / 8) + math.ceil((self.__num_lats * self.__num_lons) / 8)
            lon_idx = i % self.__num_lons
            lat_idx = math.floor(i / self.__num_lons)
            vvel[lat_idx][lon_idx] = float(self.__lines[line_idx][low_idx:high_idx])
        return WindData(idx_date, self.__grid, uvel, vvel)


class OwiNetcdf:
    def __init__(self, filename):
        self.__nc = netCDF4.Dataset(filename, "r")
        self.__grid = self.__get_grid()

    def grid(self):
        return self.__grid

    def __get_grid(self):
        lon = self.__nc["Main"].variables["lon"][0, :]
        lat = self.__nc["Main"].variables["lat"][:, 0]
        return WindGrid(lon, lat)

    def num_times(self):
        return self.__nc["Main"].variables["time"].size

    def get(self, idx):
        base_date = datetime.datetime(1990, 1, 1, 0, 0, 0)
        m_added = int(self.__nc["Main"].variables["time"][idx])
        idx_date = base_date + datetime.timedelta(minutes=m_added)
        uvel = self.__nc["Main"].variables["U10"][:][:][idx]
        vvel = self.__nc["Main"].variables["V10"][:][:][idx]
        return WindData(idx_date, self.__grid, uvel, vvel)

    def close(self):
        self.__nc.close()


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
    def __init__(self, lines, wind_inp):
        self.__lines = lines
        self.__wind_inp = wind_inp
        self.__num_lats = self.__wind_inp.num_lats()
        self.__num_lons = self.__wind_inp.num_lons()
        self.__sw_corner_lat = self.__wind_inp.s_lim()
        self.__sw_corner_lon = self.__wind_inp.w_lim()
        self.__lat_step = self.__wind_inp.spatial_res()
        self.__lon_step = self.__wind_inp.spatial_res()
        self.__grid = self.__get_grid()

    def grid(self):
        return self.__grid

    def __get_grid(self):
        lat = numpy.linspace(self.__sw_corner_lat, self.__sw_corner_lat + (self.__num_lats - 1) * self.__lat_step, self.__num_lats)
        lon = numpy.linspace(self.__sw_corner_lon, self.__sw_corner_lon + (self.__num_lons - 1) * self.__lon_step, self.__num_lons)
        return WindGrid(lon, lat)

    def get(self, idx):
        idx_date = self.__wind_inp.start_time() + datetime.timedelta(hours=idx * self.__wind_inp.time_step())
        uvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        vvel = [[None for i in range(self.__num_lons)] for j in range(self.__num_lats)]
        for i in range(self.__num_lats * self.__num_lons):
            line_idx = self.__num_lats * self.__num_lons * idx + i
            lon_idx = i % self.__num_lons
            lat_idx = self.__num_lats - math.floor(i / self.__num_lons) - 1  # WND starts in the NW corner and goes row by row
            uvel[lat_idx][lon_idx] = float(self.__lines[line_idx][0:9])
            vvel[lat_idx][lon_idx] = float(self.__lines[line_idx][10:19])
        return WindData(idx_date, self.__grid, uvel, vvel)


def dir_met_to_and_from_math(direction):
    return (270 - direction) % 360  # Formula is the same each way


def direction_from_uv(u_vel, v_vel):
    with numpy.errstate(divide="ignore"):  # Don't warn for divide by 0
        dir_math = numpy.rad2deg(numpy.arctan(numpy.divide(v_vel, u_vel)))
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
    input_wind, input_wback, wfmt, wbackfmt, z0_wr, z0_wbackr, z0_hr, z0_directional_interpolant, sl, \
        lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0 = subd_inputs
    if (wfmt == "owi-ascii") | (wfmt == "owi-netcdf"):
        z0_wr_w_grid = z0_to_wind_res(z0_wr, input_wind)
    elif wfmt == "wnd":
        z0_wr_w_grid = z0_wr
    if sl == "adcirc":
        # Interpolate z0_wr to z0_hr resolution and blend if necessary
        if input_wback is not None:
            # Scale input_wback to same roughness as input_wind, then blend
            input_wback_w_grid = wind_to_wind_res(input_wback, input_wind)
            z0_wbackr_w_grid = z0_to_wind_res(z0_wbackr, input_wind)
            input_wback_scaled = adcirc_scaling(input_wback_w_grid, z0_wbackr_w_grid.land_rough(), z0_wr_w_grid.land_rough())
            wind_w_grid = blend(input_wind, input_wback_scaled, lon_ctr_interpolant,
                                lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0)
        else:
            wind_w_grid = input_wind
        z0_wr_hr_grid = z0_to_z0_res(z0_wr_w_grid, z0_hr)
    elif sl == "up-down":
        # Scale up to z_ref and blend if necessary
        input_wind_z_ref = ten_to_zref(z0_wr_w_grid.land_rough(), input_wind)
        if input_wback is not None:
            z0_wbackr_wback_grid = z0_to_wind_res(z0_wbackr, input_wback)
            input_wback_z_ref = ten_to_zref(z0_wbackr_wback_grid.land_rough(), input_wback)
            input_wback_z_ref_w_grid = wind_to_wind_res(input_wback_z_ref, input_wind)
            wind_w_grid = blend(input_wind_z_ref, input_wback_z_ref_w_grid, lon_ctr_interpolant,
                                lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0)
        else:
            wind_w_grid = input_wind_z_ref
    # Determine z0 based on wind direction, then scale wind with directional z0
    z0_hr_grid = WindGrid(z0_hr.lon(), z0_hr.lat())
    wind_hr_grid = wind_to_z0_res(wind_w_grid, z0_hr)
    dir_hr_grid = direction_from_uv(wind_hr_grid.u_velocity(), wind_hr_grid.v_velocity())
    z0_hr_directional = z0_directional_interpolant((z0_hr_grid.lat(), z0_hr_grid.lon(), dir_hr_grid))
    if sl == "adcirc":
        wind_out = adcirc_scaling(wind_hr_grid, z0_wr_hr_grid.land_rough(), z0_hr_directional)
    elif sl == "up-down":
        wind_out = zref_to_ten(z0_hr_directional, wind_hr_grid)
    return wind_out


def adcirc_scaling(wind_inp, z0_inp, z0_tgt):
    # NOTE: This function assumes all inputs have the same spatial resolution
    u_scaled = wind_inp.u_velocity() * (z0_tgt / z0_inp)**0.0706 * numpy.log(10 / z0_tgt) / numpy.log(10 / z0_inp)
    v_scaled = wind_inp.v_velocity() * (z0_tgt / z0_inp)**0.0706 * numpy.log(10 / z0_tgt) / numpy.log(10 / z0_inp)
    return WindData(wind_inp.date(), wind_inp.wind_grid(), u_scaled, v_scaled)


def wind_to_wind_res(wind_inp, wind_tgt):
    # Interpolate a WindData object to the spatial resolution of another WindData object
    u_interp = scipy.interpolate.RectBivariateSpline(wind_inp.wind_grid().lat1d(), wind_inp.wind_grid().lon1d(), wind_inp.u_velocity(), kx=1, ky=1)
    u_wind_tgt_res = u_interp(wind_tgt.wind_grid().lat1d(), wind_tgt.wind_grid().lon1d())
    v_interp = scipy.interpolate.RectBivariateSpline(wind_inp.wind_grid().lat1d(), wind_inp.wind_grid().lon1d(), wind_inp.v_velocity(), kx=1, ky=1)
    v_wind_tgt_res = v_interp(wind_tgt.wind_grid().lat1d(), wind_tgt.wind_grid().lon1d())
    return WindData(wind_inp.date(), wind_tgt.wind_grid(), u_wind_tgt_res, v_wind_tgt_res)


def wind_to_z0_res(wind, z0):
    # Interpolate a WindData object to the spatial resolution of a Roughness object
    u_interp = scipy.interpolate.RectBivariateSpline(wind.wind_grid().lat1d(), wind.wind_grid().lon1d(), wind.u_velocity(), kx=1, ky=1)
    u_z0_res = u_interp(z0.lat(), z0.lon())
    v_interp = scipy.interpolate.RectBivariateSpline(wind.wind_grid().lat1d(), wind.wind_grid().lon1d(), wind.v_velocity(), kx=1, ky=1)
    v_z0_res = v_interp(z0.lat(), z0.lon())
    return WindData(wind.date(), WindGrid(z0.lon(), z0.lat()), u_z0_res, v_z0_res)


def z0_to_wind_res(z0, wind):
    # Interpolate a Roughness object to the spatial resolution of a WindData object
    z0_wr_interp = scipy.interpolate.RectBivariateSpline(z0.lat(), z0.lon(), z0.land_rough(), kx=1, ky=1)
    z0_w_res = z0_wr_interp(wind.wind_grid().lat1d(), wind.wind_grid().lon1d())
    return Roughness(wind.wind_grid().lon1d(), wind.wind_grid().lat1d(), z0_w_res)


def z0_to_z0_res(z0_inp, z0_tgt):
    # Interpolate a Roughness object to the spatial resolution of another Roughness object
    z0_wr_interp = scipy.interpolate.RectBivariateSpline(z0_inp.lat(), z0_inp.lon(), z0_inp.land_rough(), kx=1, ky=1)
    z0_w_res = z0_wr_interp(z0_tgt.lat(), z0_tgt.lon())
    return Roughness(z0_tgt.lon(), z0_tgt.lat(), z0_w_res)


def ten_to_zref(z0, wind):
    # Scale using equations 9 & 10 here: https://dr.lib.iastate.edu/handle/20.500.12876/1131
    z_ref = 80  # Per Isaac the logarithmic profile only applies in the near surface layer, which extends roughly 80m up; to verify with lit review
    b = 1 / (numpy.log(10) - numpy.log(z0))  # Eq 10
    uvel = wind.u_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
    vvel = wind.v_velocity() * (1 + b * numpy.log(z_ref / 10))  # Eq 9
    return WindData(wind.date(), wind.wind_grid(), uvel, vvel)


def zref_to_ten(z0, wind):
    # Scale using equations 9 & 10 here: https://dr.lib.iastate.edu/handle/20.500.12876/1131
    z_ref = 80  # Per Isaac the logarithmic profile only applies in the near surface layer, which extends roughly 80m up; to verify with lit review
    b = 1 / (numpy.log(10) - numpy.log(z0))  # Eq 10
    uvel = wind.u_velocity() / (1 + b * numpy.log(z_ref / 10))  # Eq 9
    vvel = wind.v_velocity() / (1 + b * numpy.log(z_ref / 10))  # Eq 9
    return WindData(wind.date(), wind.wind_grid(), uvel, vvel)


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


def blend(param_wind, back_wind, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0):
    # NOTE: This function assumes back_wind and param_wind have the same spatial and temporal resolution
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
    u_blend[blend_mask] = (alpha[blend_mask] * param_wind.u_velocity()[blend_mask]) + ((1 - alpha[blend_mask]) * back_wind.u_velocity()[blend_mask])
    v_blend[blend_mask] = (alpha[blend_mask] * param_wind.v_velocity()[blend_mask]) + ((1 - alpha[blend_mask]) * back_wind.v_velocity()[blend_mask])
    u_blend[back_mask] = back_wind.u_velocity()[back_mask]
    v_blend[back_mask] = back_wind.v_velocity()[back_mask]
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
        subd_z0_hr[i] = Roughness(z0_hr.lon(), z0_hr.lat()[int(subd_start_index[i]):int(subd_end_index[i])],
                                  z0_hr.land_rough()[int(subd_start_index[i]):int(subd_end_index[i]), :])
        subd_z0_directional_interpolant[i] = scipy.interpolate.RegularGridInterpolator((z0_directional_interpolant.grid[0][int(subd_start_index[i]):int(subd_end_index[i])],
                                                                                        z0_directional_interpolant.grid[1][:], z0_directional_interpolant.grid[2][:]),
                                                                                       z0_directional_interpolant.values[int(subd_start_index[i]):int(subd_end_index[i]), :, :], method='linear')
    return subd_z0_hr, subd_z0_directional_interpolant, subd_start_index, subd_end_index


def subd_restitch_domain(subd_wind_scaled, subd_start_index, subd_end_index, hr_shape, threads):
    u_scaled = numpy.zeros(hr_shape)
    v_scaled = numpy.zeros(hr_shape)
    for i, subd in enumerate(subd_wind_scaled):
        u_scaled[int(subd_start_index[i]):int(subd_end_index[i]), :] = subd.u_velocity()
        v_scaled[int(subd_start_index[i]):int(subd_end_index[i]), :] = subd.v_velocity()
        if i == 0:
            date = subd.date()
    return u_scaled, v_scaled, date


def is_valid(args):
    if args.wfmt == args.wbackfmt:
        print("ERROR: wfmt and wbackfmt cannot match. Please try again.", flush=True)
    elif args.sl != "adcirc" and args.sl != "up-down":
        print("ERROR: Unsupported scaling logic. Please try again.", flush=True)
    elif args.wfmt != "owi-ascii" and args.wfmt != "owi-netcdf" and args.wfmt != "wnd":
        print("ERROR: Unsupported wind format. Please try again.", flush=True)
    elif args.wback is not None and args.wbackfmt != "owi-ascii" and args.wbackfmt != "owi-netcdf":
        print("ERROR: Unsupported background wind format. Please try again.", flush=True)
    elif args.wback is not None and args.wfmt != "wnd":
        print("ERROR: wfmt must be wnd if wback is provided. Please try again.", flush=True)
    elif args.wbackfmt is None and args.wback is not None:
        print("ERROR: wbackfmt is required if wback is provided. Please try again.", flush=True)
    elif args.wr is None and (args.wfmt == "owi-ascii" or args.wfmt == "owi-netcdf"):
        print("ERROR: wr is required when wfmt is owi-ascii or owi-netcdf. Please try again.", flush=True)
    elif args.wbackr is None and (args.wbackfmt == "owi-ascii" or args.wbackfmt == "owi-netcdf"):
        print("ERROR: wbackr is required when wbackfmt is owi-ascii or owi-netcdf. Please try again.", flush=True)
    elif args.winp is None and args.wfmt == "wnd":
        print("ERROR: winp is required if wfmt is wnd. Please try again.", flush=True)
    else:
        return True
    return False


def build_parser():
    parser = argparse.ArgumentParser(description="Scale and subset input wind data based on high-resolution land roughness")
    parser.add_argument("-hr", metavar="highres_roughness", type=str, help="High-resolution land roughness file", required=True)
    parser.add_argument("-o", metavar="outfile", type=str, help="Name of output file to be created", required=False, default="scaled_wind")
    parser.add_argument("-r", metavar="radius", type=int,
                        help="Sector radius for directional z0 calculation, in meters; will be ignored if z0sv is false", required=False, default=3000)
    parser.add_argument("-sigma", metavar="sigma", type=int,
                        help="Weighting parameter for directional z0 calculation, in meters; will be ignored if z0sv is false", required=False, default=1000)
    parser.add_argument("-sl", metavar="scale_logic", type=str,
                        help="Which logic to use for the directional z0 adjustment. Supported values: adcirc, up-down", required=False, default='adcirc')
    parser.add_argument("-t", metavar="threads", type=int,
                        help="Number of threads to use for calculations; must not exceed the number available; total threads = t + wasync", required=False, default=1)
    parser.add_argument("-w", metavar="wind", type=str, help="Wind file to be scaled and subsetted", required=True)
    parser.add_argument("-wasync", help="Add this flag to begin scaling winds for the next time step while writing the output for the current time step; "
                        + "writes run in series and are thread safe, but peak memory use may be high if write times are slower than computation times; "
                        + "total threads = t + wasync", action='store_true', required=False, default=False)
    parser.add_argument("-wback", metavar="wind_background", type=str,
                        help="Background wind to be blended with the wind file; if included, w and wback will be blended", required=False)
    parser.add_argument("-wbackfmt", metavar="wback_format", type=str,
                        help="Format of the input background wind file. Supported values: owi-ascii, owi-netcdf. Required if wback is provided.", required=False)
    parser.add_argument("-wbackr", metavar="wback_roughness", type=str,
                        help="Wind-resolution land roughness file; required if wbackfmt is owi-ascii or owi-netcdf", required=False)
    parser.add_argument("-wfmt", metavar="w_format", type=str,
                        help="Format of the input wind file. Supported values: owi-ascii, owi-netcdf, wnd. If wback is provided, this must be wnd.", required=True)
    parser.add_argument("-winp", metavar="wind_inp", type=str,
                        help="Wind_Inp.txt metadata file; required if wfmt is wnd", required=False)
    parser.add_argument("-wr", metavar="wind_roughness", type=str,
                        help="Wind-resolution land roughness file; required if wfmt is owi-ascii or owi-netcdf", required=False)
    parser.add_argument("-z0sv", help="Add this flag to generate and save off a directional z0 interpolant; do this in advance to save time during regular runs",
                        action='store_true', required=False, default=False)
    parser.add_argument("-z0name", metavar="z0_name", type=str,
                        help="Name of directional z0 interpolant file; it will be generated if z0sv is True and loaded if z0sv is False", required=False, default='z0_interp')
    return parser


def main():
    start = datetime.datetime.now()

    # Read and validate the command line arguments
    parser = build_parser()
    args = parser.parse_args()
    if not is_valid(args):
        return

    # Create wind files, set num_times
    if args.wfmt == "owi-ascii":
        win_file = open(args.w, 'r')
        lines = win_file.readlines()
        win_file.close()
        owi_ascii = OwiAsciiWind(lines)
        num_times = owi_ascii.num_times()
    elif args.wfmt == "owi-netcdf":
        owi_netcdf = OwiNetcdf(args.w)
        num_times = owi_netcdf.num_times()
    elif args.wfmt == "wnd":
        metadata = WndWindInp(args.winp)
        num_times = metadata.num_times()
        wnd_file = open(args.w, 'r')
        lines = wnd_file.readlines()
        wnd_file.close()
        wnd = WndWind(lines, metadata)
    if args.wbackfmt == "owi-ascii":
        win_file = open(args.wback, 'r')
        lines = win_file.readlines()
        win_file.close()
        owi_ascii = OwiAsciiWind(lines)
    elif args.wbackfmt == "owi-netcdf":
        owi_netcdf = OwiNetcdf(args.wback)

    # If blending, generate interpolants used for every time slice
    if args.wback is not None:
        lon_ctr_interpolant, lat_ctr_interpolant, time_ctr_date_0 = generate_ctr_interpolant()
        rmw_interpolant, time_rmw_date_0 = generate_rmw_interpolant()

    # Define roughness grids
    if (args.wfmt == "owi-ascii") | (args.wfmt == "owi-netcdf"):
        wr_lon, wr_lat, wr_land_rough = Roughness.get(args.wr)
        z0_wr = Roughness(wr_lon, wr_lat, wr_land_rough)
    elif args.wfmt == "wnd":
        z0_wnd = 0.0033
        wr_land_rough = numpy.zeros((metadata.num_lats(), metadata.num_lons())) + z0_wnd  # z0_wr defined below, after wnd grid is available
    if (args.wbackfmt == "owi-ascii") | (args.wbackfmt == "owi-netcdf"):
        wbackr_lon, wbackr_lat, wbackr_land_rough = Roughness.get(args.wbackr)
        z0_wbackr = Roughness(wbackr_lon, wbackr_lat, wbackr_land_rough)
    hr_lon, hr_lat, hr_land_rough = Roughness.get(args.hr)
    z0_hr = Roughness(hr_lon, hr_lat, hr_land_rough)
    lon_grid, lat_grid = numpy.meshgrid(z0_hr.lon(), z0_hr.lat())

    # Generate or load directional z0 interpolants
    if args.z0sv:
        print("INFO: z0sv is True, so a directional z0 interpolant file will be generated. This will take a while.", flush=True)
        print("INFO: Generating directional z0 interpolant...", flush=True)
        z0_directional_interpolant = generate_directional_z0_interpolant(lon_grid, lat_grid, z0_hr.land_rough(), args.sigma, args.r)
        with open(args.z0name + '.pickle', 'wb') as file:
            pickle.dump(z0_directional_interpolant, file, pickle.HIGHEST_PROTOCOL)
    else:
        print("INFO: Loading directional z0 interpolant...", flush=True)
        with open(args.z0name + '.pickle', 'rb') as file:
            z0_directional_interpolant = pickle.load(file)

    # Define subdomains for multiprocessing
    subd_z0_hr, subd_z0_directional_interpolant, subd_start_index, subd_end_index = subd_prep(z0_hr, z0_directional_interpolant, args.t)

    # Scale wind one time slice at a time
    wind = None
    time_index = 0
    if args.wasync:
        write_thread = [[] for i in range(num_times)]
        lock = threading.Lock()
        did_warn = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.t) as executor:
        for time_index in range(0, num_times):
            print("INFO: Processing time slice {:d} of {:d}".format(time_index + 1, num_times), flush=True)
            subd_inputs = [[] for i in range(args.t)]
            # Generate inputs for roughness_adjust
            if args.wfmt == "owi-ascii":
                input_wind = owi_ascii.get(time_index)
            elif args.wfmt == "owi-netcdf":
                input_wind = owi_netcdf.get(time_index)
            elif args.wfmt == "wnd":
                input_wind = wnd.get(time_index)
                if time_index == 0:
                    z0_wr = Roughness(input_wind.wind_grid().lon1d(), input_wind.wind_grid().lat1d(), wr_land_rough)
            if args.wback is not None:
                if args.wbackfmt == 'owi-ascii':
                    input_wback = owi_ascii.get(time_index)
                elif args.wbackfmt == 'owi-netcdf':
                    input_wback = owi_netcdf.get(time_index)
                for i in range(0, args.t):
                    subd_inputs[i] = [input_wind, input_wback, args.wfmt, args.wbackfmt, z0_wr, z0_wbackr, subd_z0_hr[i], subd_z0_directional_interpolant[i],
                                      args.sl, lon_ctr_interpolant, lat_ctr_interpolant, rmw_interpolant, time_ctr_date_0, time_rmw_date_0]
            else:
                for i in range(0, args.t):
                    subd_inputs[i] = [input_wind, None, args.wfmt, None, z0_wr, None, subd_z0_hr[i], subd_z0_directional_interpolant[i],
                                      args.sl, None, None, None, None, None]
            # Call roughness_adjust for each subdomain
            subd_wind_scaled = executor.map(roughness_adjust, subd_inputs)
            u_scaled, v_scaled, date = subd_restitch_domain(subd_wind_scaled, subd_start_index, subd_end_index, z0_hr.land_rough().shape, args.t)
            wind_scaled = WindData(date, WindGrid(z0_hr.lon(), z0_hr.lat()), u_scaled, v_scaled)
            # Write to NetCDF; single-threaded with optional asynchronicity for now, as thread-safe NetCDF is complicated
            if not wind:
                wind = NetcdfOutput(args.o, z0_hr.lon(), z0_hr.lat())
            if args.wasync:
                if time_index > 0 and not did_warn and write_thread[time_index - 1].is_alive():
                    print("WARNING: NetCDF writes are taking longer than computations. This may result in higher memory use. "
                          + "Especially if this warning appears early, consider using fewer threads or disabling asynchronous writes.", flush=True)
                    did_warn = True
                write_thread[time_index] = threading.Thread(target=wind.append, args=(time_index, wind_scaled.date(),
                                                                                      wind_scaled.u_velocity(), wind_scaled.v_velocity(), lock))
                write_thread[time_index].start()
            else:
                wind.append(time_index, wind_scaled.date(), wind_scaled.u_velocity(), wind_scaled.v_velocity(), None)
        # If writes are asynchronous, wait for all threads to return
        if args.wasync:
            for i in range(0, num_times):
                if write_thread[i].is_alive():
                    print("INFO: Still writing output to NetCDF for time slice {:d} of {:d}".format(i + 1, num_times), flush=True)
                write_thread[i].join()

    # Clean up
    if args.wfmt == "owi-netcdf" or args.wbackfmt == "owi-netcdf":
        owi_netcdf.close()
    wind.close()
    print("RICHAMP wind generation complete. Runtime:", str(datetime.datetime.now() - start), flush=True)


if __name__ == '__main__':
    main()
