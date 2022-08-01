#!/usr/bin/env python3
# Contact: Josh Port (joshua_port@uri.edu)
# Requirements: python3, numpy
#
# This is a Python port of Xuanyu Chen's retrieve_ust_U10.m and cal_z0_from_ustar.m Matlab functions
# This version also supports vector inputs for performance reasons
#
def retrieve_ust_U10(u_obs, z_obs):
    from numpy import arange, argmin, empty, exp #, log
   
    k = 0.40    
    y = exp(k * u_obs)
    res = 0.001
    ust = arange(0, 5, res)
    z0 = cal_z0_from_ustar(ust)
    Y = empty(len(ust))
    for i in range(len(ust)):
        if z0[i] == 0 and ust[i] == 0:
            Y[0] = 1 # python throws a divide by zero error otherwise; Matlab doesn't, since the exponent is 0
        else:
            Y[i] = (z_obs / z0[i])**ust[i]
            
    # find Y closest to y and then retrieve corresponding ust_est
    ust_est = empty((len(u_obs), len(u_obs[0])))
    for i in range(len(u_obs)):
        for j in range(len(u_obs[0])):
            dif = abs(y[i,j] - Y)        
            loc = argmin(dif)
            if Y[loc] - y[i,j] > 0:
                slp = (Y[loc] - Y[loc-1]) / res
                dust = (y[i,j] - Y[loc-1]) / slp
                ust_est[i,j] = ust[loc-1] + dust
            else:
                slp = (Y[loc+1] - Y[loc]) / res
                dust = (y[i,j] - Y[loc]) / slp
                ust_est[i,j] = ust[loc] + dust
    
    # # use ust_y to calculate U10; not relevant for RICHAMP, so commenting out
    # z0_ust_est = cal_z0_from_ustar(ust_est)
    # U10 = ust_est / k * log(10.0 / z0_ust_est)
    
    return ust_est #, U10

def cal_z0_from_ustar(ust):
    # Function to calculate z0 based on 4 regimes of ustar (based on Old GFDL)   
    from numpy import array, empty, matmul
    
    z0 = empty(len(ust))
    ust_array = array([[ust**8],[ust**7],[ust**6],[ust**5],[ust**4],[ust**3],[ust**2],[ust**1],[ust**0]]).squeeze()
    
    # polynomial:
    p_b1 = array([-0.000098701949811,  0.001486209983407,
                  -0.007584567778927,  0.019487056157620,
                  -0.029314498154105,  0.024309735869547,
                  -0.006997554677642,  0.001258400989803,
                  -0.000043976208055]).reshape(1,9)
    p_b2 = array([-0.002182648458354,  0.046387047659009,
                  -0.428830523588356,  2.251251262348664,
                  -7.334368361013868, 15.163848944684784,
                  -19.388290305787166,13.970227275905133,
                  -4.319572176336596]).reshape(1,9)
    g = 9.806650;
    
    for i in range(len(ust)):
        ustar = ust[i]
        if ustar < 0.3:
            z0[i] = 0.0185 / g * ustar**2
        elif ustar < 2.35:
            p = p_b1
            z0[i] = float(matmul(p,ust_array[:,i]))
        elif ustar < 3:
            p = p_b2
            z0[i] = float(matmul(p,ust_array[:,i]))
        else:
            z0[i] = 0.001305

    return z0

# For testing
# def main():
#     u_obs = 15
#     z_obs = 5
#     ust_est = retrieve_ust_U10(u_obs, z_obs)
#     print(ust_est)
    
# if __name__ == '__main__':
#     main()





