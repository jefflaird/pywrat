import numpy as np 
import matplotlib.pyplot as plt
from pywrat import pywrat
import pandas as pd

#testing bufferflows


for year in range(1922,2003):
  for month in range(1,13):
#     print('Now Running %d-%d' % (year,month)) # now in pywrat.py
    pywrat(month,year)

# pywrat(1, 1977)