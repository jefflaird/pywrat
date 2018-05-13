##PYWRAT##

from pulp import *
import pandas as pd
import numpy as np
import operator

def pywrat(month,year):
  #Load user data
  rip_statements = pd.read_csv('input_data/RiparianStatements.csv', index_col = 0)
  rip_users = rip_statements.index.tolist() # a list of appIDs

  # - huc_user is a dict indexed by tuple (j,i) to say if user i is in huc j **hard
  huc_user = pd.read_csv('input_data/huc_user_table.csv', dtype={'HUC_12': object})
  huc_user.set_index('HUC_12', inplace=True)

  # - hucConnectivity[(j, k)], a dict where (j,k) is a tuple of two hucs
  CM = pd.read_csv('input_data/ConnectivityMatrix.csv', dtype={'HUC_12': object})
  CM.set_index('HUC_12', inplace=True)

  # - connectivity[(j,i)], a dict where (j,i) says if user i is "connected" (??) to water supply from huc j
  user_huc_con = pd.read_csv('input_data/user_huc_connectivity.csv', dtype={'HUC_12': object})
  user_huc_con.set_index('HUC_12', inplace=True)

  # a different matrix for appropriative
  APP_user_huc_con = pd.read_csv('input_data/APP_user_huc_connectivity.csv', dtype={'HUC_12': object})
  APP_user_huc_con.set_index('HUC_12', inplace=True)

  ######################################################################################
  ####Riparian LP

  day = 1
  monthnum = month
  # year = 1926

  month_strings = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER']
  dpm_array = [31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 30, 31]
  month = month_strings[monthnum-1]
  days_per_month = dpm_array[monthnum-1]
  demand = rip_statements[month] / days_per_month
  outputdate =  str(year) + '-' + str(monthnum)

  #Flow availablity
  timestr = str(monthnum) + '/' + str(day) + '/' + str(year)
  flow = pd.read_csv('input_data/HUC12_Qpred.csv', dtype={'HUC_12': object})
  hucs = flow.HUC_12.tolist()
  flow = flow.set_index('HUC_12')[timestr]

  #print LP
  print('Running Rip LP for %s' % timestr)

  #create problem
  ripLP = LpProblem("Riparian LP", LpMinimize)

  #create decision variable as dictionary
  p_catch = LpVariable.dicts("Proportion", hucs, 0, 1)
  ##p_catch is is the allocation proportion applied to all user demand in a HUC, riparian users only
  ##p_catch for any HUC cant exceed a downstream HUC

  #define allocation
  rip_allocation = {}
  for i in rip_users:
    # ASSUMES ONE HUC PER USER
    j = huc_user.index[huc_user[i] == 1].tolist()[0] 
    rip_allocation[i] = lpSum(p_catch[j] * demand[i])

  #add objective function
  subP_penalty = user_huc_con.sum(axis=1) / user_huc_con.count(axis=1)
  huc_demand = user_huc_con.multiply(demand, axis=1).sum(axis=1)
  subP_scaler = (subP_penalty / huc_demand).min()
  subP_scaler *= 0.9 # why? because.

  ripLP += subP_scaler * lpSum([p_catch[j] * subP_penalty[j] for j in hucs]) - lpSum([rip_allocation[i] for i in rip_users])

  ##constraints##
  #upstream proportions cannot exceed downstream
  for k in hucs:
    connected_hucs = CM.index[CM[k] == 1].tolist()
    for j in connected_hucs:
      ripLP += p_catch[j] >= p_catch[k]

  #sum of allocation, per huc, cannot be greater than available
  for j in hucs:
    uhcT = user_huc_con.transpose()
    users_in_huc = uhcT.index[uhcT[j] == 1].tolist()

    ripLP += lpSum([rip_allocation[i] for i in users_in_huc]) <= flow[j]
    # CHECK: use "flow" or update to include environmental flow fractions
    # don't need to index connectivity in the obj function because we know it's = 1

  # allocation must be greater than public health and safety (phs) requirements
  # NOTE add PHS data later when we have it
  # for i in users:
  #   allocation[i] >= phs[i]

  # The problem is solved using PuLP's choice of Solver
  ripLP.solve()

  print('Status:', LpStatus[ripLP.status])
  print('Objective = ', value(ripLP.objective))

  # export results to file
  huc_results = {}
  for j in hucs:
    huc_results[j] = p_catch[j].varValue

  # huc_results = pd.DataFrame.from_dict(huc_results, orient='index')
  # huc_results.columns = ['p_catch']

  ripres = pd.DataFrame(rip_users)
  ripres.columns = ['App ID']

  rip_hucs = rip_statements['HUC_12'].tolist()
  ripres.insert(1, 'HUC-12', rip_hucs)

  ripres.insert(0, 'Pull Date', timestr)

  ripres_demand = demand.tolist()
  ripres.insert(3, 'Demand', ripres_demand)

  ripres_allo = [0] * len(rip_hucs)
  for j in np.arange(len(rip_users)):
    ripres_allo[j] = huc_results[str(rip_hucs[j])] * ripres_demand[j]
  ripres.insert(4, 'Allocation', ripres_allo)

  ripres.insert(5, 'Right Type', 'Riparian')

  ripres_active = [0] * len(rip_hucs)
  for j in np.arange(len(ripres_active)):
    if ripres_demand[j] == 0:
      ripres_active[j] = False
    else:
      ripres_active[j] = True
  ripres.insert(6, 'Active?', ripres_active)

  ripres.insert(7, 'File Date', rip_statements['File Date'])

  ripres_short = list(map(operator.sub, ripres_demand, ripres_allo))
  ripres.insert(8, 'Shortage', ripres_short)

  ripres_short_by_right = [0] * len(rip_hucs)
  for j in np.arange(len(ripres_active)):
    if ripres_allo[j] == ripres_demand[j]:
      ripres_short_by_right[j] = False
    else:
      ripres_short_by_right[j] = True
  ripres.insert(9, 'Allocation Constrained via Right', ripres_short_by_right)

  ripres_short_by_short = [0] * len(rip_hucs)
  for j in np.arange(len(ripres_active)):
    if ripres_allo[j] != ripres_demand[j]:
      ripres_short_by_short[j] = True
    else:
      ripres_short_by_short[j] = False
  ripres.insert(10, 'Allocation Constrained via Shortage', ripres_short_by_short)

  ripres_short_by_health = [0] * len(rip_hucs)
  ripres.insert(11, 'Allocation Constrained via Public Health', ripres_short_by_health)

  #     ripres_HUC_flow = #flow left in HUC (after appropriative? will have to move to end)
  #     ripres_percentDemand = #ripres_Allocation[j] / ripres_Demand[j]

  ripres.set_index('App ID')
  ripres.to_csv('results/%s_riparian_resultstest.csv' % (outputdate))

  #######################################################################################
  ##### Appropriative LP

  #Load user data
  app_statements = pd.read_csv('input_data/AppropriativeStatements.csv', index_col = 0)
  app_users = app_statements.index.tolist() # a list of appIDs
  # app priority determined by year of first use for pre-1914, same year = same priority

  # - priority: a dict containing priority rank (1 to N) for each user (app only)
  priority = app_statements['Priority']

  #print LP
  print('Running App LP for %s' % timestr)

  # Creates the variable to contain the problem data
  appLP = LpProblem("Appropriative LP",LpMinimize)

  # A dictionary called 'Vars' is created to contain the referenced variables
  allocation = LpVariable.dicts("Allocation", app_users, 0, None)

  # daily demand
  demand = app_statements[month] / days_per_month

  # The objective function is added to 'prob' first
  appLP += lpSum([(demand[i] - allocation[i]) * ((len(app_users) + 1)- priority[i]) for i in app_users])
  # The statement (len(users)+1)-priority[i]) in the obj function is the shortage penalty modifer

  # allocation must be less than demand
  for i in app_users:
      appLP += allocation[i] <= demand[i]

  # allocation from rip should be subtracted from available water for appropriative
  app_available = {}

  for j in hucs:

    # Need riparian "users in huc" first
    uhcT = user_huc_con.transpose()
    users_in_huc = uhcT.index[uhcT[j] == 1].tolist()
    app_available[j] = flow[j]

    # need to subtract ".value()" so that it's a number instead of a PuLP expression
    for k in users_in_huc:
      app_available[j] -= rip_allocation[k].value()

    if app_available[j] < 0:
      app_available[j] = 0

    # then get appropriative users in huc
    uhcT = APP_user_huc_con.transpose()
    APP_users_in_huc = uhcT.index[uhcT[j] == 1].tolist()

    # allocation sum, per HUC, must be less than available flow in HUC
    appLP += lpSum([allocation[i] for i in APP_users_in_huc]) <= app_available[j]
      
  # # allocation must be greater than public health and safety requirements(phs)
  # for i in users:
  #     appLP += allocation[i] >= phs[i]

  # The problem is solved using PuLP's choice of Solver
  appLP.solve()

  print("Status:", LpStatus[appLP.status])
  print("Objective = ", value(appLP.objective))

  # export results to file
  app_results = {}
  for i in app_users:
    app_results[i] = allocation[i].varValue
  app_results = pd.DataFrame.from_dict(app_results, orient='index')
  app_results.columns = ['allocation']

  appres = pd.DataFrame(app_users)
  appres.columns = ['App ID']

  app_hucs = app_statements['HUC_12'].tolist()
  appres.insert(1, 'HUC-12', app_hucs)

  appres.insert(0, 'Pull Date', timestr)

  appres_demand = demand.tolist()
  appres.insert(3, 'Demand', appres_demand)

  appres_allo = [0] * len(app_results['allocation'])
  for j in np.arange(len(app_users)):
    appres_allo[j] = app_results['allocation'][j]
  appres.insert(4, 'Allocation', appres_allo)
  
  appres_type = [0] * len(app_hucs)
  # use file date and separate Pre and Post 1914
  appres.insert(5, 'Right Type', 'Appropriative')

  appres_active = [0] * len(app_hucs)
  for j in np.arange(len(appres_active)):
    if appres_demand[j] == 0:
      appres_active[j] = False
    else:
      appres_active[j] = True
  appres.insert(6, 'Active?', appres_active)

  appres.insert(7, 'File Date', app_statements['File Date'])

  appres_short = list(map(operator.sub, appres_demand, appres_allo))
  appres.insert(8, 'Shortage', appres_short)

  appres_short_by_right = [0] * len(app_hucs)
  for j in np.arange(len(appres_active)):
    if appres_allo[j] == appres_demand[j]:
      appres_short_by_right[j] = False
    else:
      appres_short_by_right[j] = True
  appres.insert(9, 'Allocation Constrained via Right', appres_short_by_right)

  appres_short_by_short = [0] * len(app_hucs)
  for j in np.arange(len(appres_active)):
    if appres_allo[j] != appres_demand[j]:
      appres_short_by_short[j] = True
    else:
      appres_short_by_short[j] = False
  appres.insert(10, 'Allocation Constrained via Shortage', appres_short_by_short)

  appres_short_by_health = [0] * len(app_hucs)
  appres.insert(11, 'Allocation Constrained via Public Health', appres_short_by_health)

  appres.set_index('App ID')
  appres.to_csv('results/%s_app_allocationtest.csv' % (outputdate))