# pywrat

This is  a python version of the Drought Water Rights Allocation Tool as developed by researchers at the UC Davis Center for Watershed Sciences. The goal of this project is to use purely python to replicate this spreadsheet model containing the SovlerStudio add-in and the python linear program solver PuLP.

To run the model (currently only the Sacramento model):
- Clone the repository
- In the pywrat.py file, you can edit/specify your which results to output and where they will be stored (lines 106 and 184)
  - Right now, outputs are decision variables (P-catchments for Riparian LP, and User allocations for Appropriative LP)
- In the main.py file, chose the date or date range over which you would like to run
- Check out your results!
