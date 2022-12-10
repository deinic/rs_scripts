
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt

import matplotlib.pyplot as plt
import numpy as np
import os
import time
import snappy



from snappy import jpy
from snappy import ProductIO
from snappy import Product
from snappy import ProductUtils
from snappy import WKTReader
from snappy import HashMap
from snappy import GPF



# get start stime 
start = time.asctime( time.localtime(time.time()) ) 

#get map.geojson polygon for our region  of interest
footprint = geojson_to_wkt(read_geojson('map.geojson'))

#fecth data form sentinelsat catalog
'''
api = SentinelAPI('username', 'password', 'https://apihub.copernicus.eu/apihub')

products = api.query(footprint,
                     date = ('20211215', '20211217'),
                     platformname = 'Sentinel-1',
                     producttype='GRD')

products_df = api.to_dataframe(products) 


# download first results from the search
#api.download(products_df['uuid'][0])


filename=products_df['title'][0]+'.zip' '''
filename='S1B_IW_GRDH_1SDV_20211216T180247_20211216T180312_030054_0396AA_5E0C.zip'
# Display some information from file

product = ProductIO.readProduct(filename)
width = product.getSceneRasterWidth()
print("Width: {} px".format(width)) 
width = product.getSceneRasterWidth()
print("Width: {} px".format(width))
height = product.getSceneRasterHeight()
print("Height: {} px".format(height))
name = product.getName()
print("Name: {}".format(name))
band_names = product.getBandNames()
print("Band names: {}".format(", ".join(band_names)))
proj= """GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]"""

#Processing stages
# Apply-Orbit-File -> removeThermalNoise -> Calibration -> Speckle-Filter -> Terrain-Correction -> Subset

# Invoke an HasMap object for defining parameters in each stage
parameters = HashMap()


#OrbitFile

parameters.put('Apply-Orbit-File', True)
apply_orbit = GPF.createProduct('Apply-Orbit-File', parameters, product)
print("***OrbitFile done!***")

#ThermalNoise

parameters.put('removeThermalNoise', True)
thermal_noise = GPF.createProduct('ThermalNoiseRemoval', parameters, apply_orbit)
print("***ThermalNoise done!***")


#Calibration
parameters.put('outputSigmaBand', True)
parameters.put('sourceBands', 'Intensity_VH,Intensity_VV')
parameters.put('selectedPolarisations', 'VH,VV')
parameters.put('outputImageScaleInDb', False)
calibrated = snappy.GPF.createProduct("Calibration", parameters, thermal_noise)
print("***Calibration done!***")


#Speckle-Filter
parameters = HashMap()
parameters.put('filter', 'Refined Lee')
parameters.put('filterSizeX', 5)
parameters.put('filterSizeY', 5)
speckle = GPF.createProduct('Speckle-Filter', parameters, calibrated)
print("***Speckle-Filter done!***")

#Terrain-Correction

parameters.put('demName', 'SRTM 3Sec')
parameters.put('imgResamplingMethod', 'BILINEAR_INTERPOLATION')
parameters.put('pixelSpacingInMeter', 10.0)
parameters.put('mapProjection', proj)                
parameters.put('nodataValueAtSea', False) 
parameters.put('saveSelectedSourceBand', True)
terrain_correction = GPF.createProduct('Terrain-Correction', parameters, speckle)
print("***Terrain-Correction done!***")


terrain_correction_db = GPF.createProduct('LinearToFromdB', parameters, terrain_correction)


#Subset

parameters.put('CopyMetadata', True)
parameters.put('geoRegion', footprint)
subset= GPF.createProduct('Subset', parameters,terrain_correction_db)

print("***Subset done!***")
#ProductIO.writeProduct(subset,'Subset_Orb_TN_Cal_SpK_TC.dim',"BEAM-DIMAP")
print("***Subset Written!***")

#PLOT

p = ProductIO.readProduct('Subset_Orb_TN_Cal_SpK_TC.dim')
sigma0_VV = p.getBand('Sigma0_VV_db')
w = sigma0_VV.getRasterWidth()
h = sigma0_VV.getRasterHeight()
sigma0_VV_data = np.zeros(w * h, np.float32)
sigma0_VV.readPixels(0, 0, w, h, sigma0_VV_data)
p.dispose()
sigma0_VV_data.shape = h, w
plt.imshow(sigma0_VV_data,cmap='gray')
plt.show()
plt.hist(sigma0_VV_data)
plt.show()


#imgplot.write_png('sigma0_VV_data.png')



print("***Creating Flood Mask......***")

#BandMath - Binarization Water 
BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')

targetBand0 = BandDescriptor()
targetBand0.name = 'FloodMask'
targetBand0.type = 'float32'
targetBand0.expression = 'if Sigma0_VV_db<-19 then 1 else 0'

targetBands = jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1) #(,1 is array-size depend on number of bandMath)
targetBands[0] = targetBand0
parameters.put('targetBands', targetBands)

flood_mask = GPF.createProduct('BandMaths', parameters, subset)

#Write Product
ProductIO.writeProduct(flood_mask,'Subset_Orb_TN_Cal_SpK_TC_FloodMask.dim',"BEAM-DIMAP")

print("***Write flood_mask Product done!***")


print('Start Process at: ', start)
print('End Process at: ',time.asctime( time.localtime(time.time()) ))


