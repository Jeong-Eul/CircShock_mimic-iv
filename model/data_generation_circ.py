import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from sklearn.preprocessing import LabelEncoder
import pickle
import datetime
import os
import sys
from pathlib import Path
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('mode.chained_assignment',  None) 

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + './../..')
if not os.path.exists("./data/dict"):
    os.makedirs("./data/dict")
if not os.path.exists("./data/csv"):
    os.makedirs("./data/csv")
    
class Generator():
    def __init__(self, cohort_output, if_mort, if_admn, if_los, feat_cond, feat_lab, feat_proc, feat_out, feat_chart, feat_med, feat_ing, impute, include_time, bucket, predW=1):
        self.feat_cond,self.feat_proc,self.feat_out,self.feat_chart,self.feat_med,self.feat_lab, self.feat_ing = feat_cond,feat_proc,feat_out,feat_chart,feat_med,feat_lab,feat_ing
        self.cohort_output=cohort_output
        self.impute=impute
        self.data = self.generate_adm()
        print("[ READ COHORT ]")
        bucket = 1
        self.generate_feat()
        print("[ READ ALL FEATURES ]")
        
        if if_mort:
            self.mortality_length(include_time,predW)
            print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
        elif if_admn:
            self.readmission_length(include_time)
            print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
        elif if_los:
            self.los_length(include_time)
            print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
            
        if bucket == 1:
            
            final_meds = meds[(meds['start_time']>0)&(meds['stop_time']>0)].copy()
            final_ing= ing[(ing['start_time']>0)&(ing['stop_time']>0)].copy()
            final_proc= proc.copy() 
            final_out= out.copy()
            final_chart= chart.copy()
            final_labs= labs.copy()

            feat_med = True
            feat_ing = True
            feat_proc = True
            feat_out = True
            feat_chart = True
            impute = True
            feat_lab = True
            
            self.create_Dict(final_meds,final_proc,final_out,final_chart,final_labs,final_ing)
        else: 
            self.smooth_meds(bucket)
        print("[ SUCCESSFULLY SAVED DATA DICTIONARIES ]")
    
    def generate_feat(self):
        if(self.feat_ing):
            print("[ ======READING INGREDIENT ]")
            self.generate_ing()
        if(self.feat_chart):
            print("[ ======READING CHART EVENTS ]")
            self.generate_chart()
        if(self.feat_lab):
            print("[ ======READING LABS ]")
            self.generate_labs()
            self.get_stay_id()
        if(self.feat_cond):
            print("[ ======READING DIAGNOSIS ]")
            self.generate_cond()
        if(self.feat_proc):
            print("[ ======READING PROCEDURES ]")
            self.generate_proc()
        if(self.feat_out):
            print("[ ======READING OUT EVENTS ]")
            self.generate_out()
        if(self.feat_med):
            print("[ ======READING MEDICATIONS ]")
            self.generate_meds()

    def generate_adm(self):
        data=pd.read_csv(f"./data/cohort/{self.cohort_output}.csv.gz", compression='gzip', header=0, index_col=None)
        data['intime'] = pd.to_datetime(data['intime'])
        data['outtime'] = pd.to_datetime(data['outtime'])
        data['los']=pd.to_timedelta(data['outtime']-data['intime'],unit='h')
        data['los']=data['los'].astype(str)
        data[['days', 'dummy','hours']] = data['los'].str.split(' ', -1, expand=True)
        data[['hours','min','sec']] = data['hours'].str.split(':', -1, expand=True)
        data['los']=pd.to_numeric(data['days'])*24+pd.to_numeric(data['hours'])
        data=data.drop(columns=['days', 'dummy','hours','min','sec'])
        data=data[data['los']>0]
        data['Age']=data['Age'].astype(int)
        #print(data.head())
        #print(data.shape)
        return data
    
    def generate_cond(self):
        cond=pd.read_csv("./data/features/preproc_diag_icu.csv.gz", compression='gzip', header=0, index_col=None)
        cond=cond[cond['stay_id'].isin(self.data['stay_id'])]
        cond_per_adm = cond.groupby('stay_id').size().max()
        self.cond, self.cond_per_adm = cond, cond_per_adm
    
    def generate_proc(self):
        proc=pd.read_csv("./data/features/preproc_proc_icu.csv.gz", compression='gzip', header=0, index_col=None)
        proc=proc[proc['stay_id'].isin(self.data['stay_id'])]
        proc[['start_days', 'dummy','start_hours']] = proc['event_time_from_admit'].str.split(' ', -1, expand=True)
        proc[['start_hours','min','sec']] = proc['start_hours'].str.split(':', -1, expand=True)
        proc['start_time']=pd.to_numeric(proc['start_days'])*24+pd.to_numeric(proc['start_hours'])
        proc=proc.drop(columns=['start_days', 'dummy','start_hours','min','sec'])
        proc=proc[proc['start_time']>=0]
        
        ###Remove where event time is after discharge time
        proc=pd.merge(proc,self.data[['stay_id','los']],on='stay_id',how='left')
        proc['sanity']=proc['los']-proc['start_time']
        proc=proc[proc['sanity']>0]
        del proc['sanity']
        
        self.proc=proc
        
    def generate_out(self):
        out=pd.read_csv("./data/features/preproc_out_icu.csv.gz", compression='gzip', header=0, index_col=None)
        out=out[out['stay_id'].isin(self.data['stay_id'])]
        out[['start_days', 'dummy','start_hours']] = out['event_time_from_admit'].str.split(' ', -1, expand=True)
        out[['start_hours','min','sec']] = out['start_hours'].str.split(':', -1, expand=True)
        out['start_time']=pd.to_numeric(out['start_days'])*24+pd.to_numeric(out['start_hours'])
        out=out.drop(columns=['start_days', 'dummy','start_hours','min','sec'])
        out=out[out['start_time']>=0]
        
        ###Remove where event time is after discharge time
        out=pd.merge(out,self.data[['stay_id','los']],on='stay_id',how='left')
        out['sanity']=out['los']-out['start_time']
        out=out[out['sanity']>0]
        del out['sanity']
        
        self.out=out
        
        
    def generate_chart(self):
        chunksize = 5000000
        final=pd.DataFrame()
        for chart in tqdm(pd.read_csv("./data/features/preproc_chart_icu.csv.gz", compression='gzip', header=0, index_col=None,chunksize=chunksize)):
            chart=chart[chart['stay_id'].isin(self.data['stay_id'])]
            chart[['start_days', 'dummy','start_hours']] = chart['event_time_from_admit'].str.split(' ', -1, expand=True)
            chart[['start_hours','min','sec']] = chart['start_hours'].str.split(':', -1, expand=True)
            chart['start_time']=pd.to_numeric(chart['start_days'])*24+pd.to_numeric(chart['start_hours'])
            chart=chart.drop(columns=['start_days', 'dummy','start_hours','min','sec','event_time_from_admit'])
            chart=chart[chart['start_time']>=0]

            ###Remove where event time is after discharge time
            chart=pd.merge(chart,self.data[['stay_id','los']],on='stay_id',how='left')
            chart['sanity']=chart['los']-chart['start_time']
            chart=chart[chart['sanity']>0]
            del chart['sanity']
            del chart['los']
            
            if final.empty:
                final=chart
            else:
                final=final.append(chart, ignore_index=True)
        
        self.chart=final
        
    
    def generate_labs(self):
        chunksize = 10000000
        final=pd.DataFrame()
        for labs in tqdm(pd.read_csv("./data/features/preproc_labs.csv.gz", compression='gzip', header=0, index_col=None,chunksize=chunksize)):
            labs=labs[labs['hadm_id'].isin(self.data['hadm_id'])]
            labs[['start_days', 'dummy','start_hours']] = labs['lab_time_from_admit'].str.split(' ', -1, expand=True)
            labs[['start_hours','min','sec']] = labs['start_hours'].str.split(':', -1, expand=True)
            labs['start_time']=pd.to_numeric(labs['start_days'])*24+pd.to_numeric(labs['start_hours'])
            labs=labs.drop(columns=['start_days', 'dummy','start_hours','min','sec'])
            labs=labs[labs['start_time']>=0]

            ###Remove where event time is after discharge time
            labs=pd.merge(labs,self.data[['hadm_id','los']],on='hadm_id',how='left')
            labs['sanity']=labs['los']-labs['start_time']
            labs=labs[labs['sanity']>0]
            del labs['sanity']
            
            if final.empty:
                final=labs
            else:
                final=final.append(labs, ignore_index=True)

        self.labs=final
        
        
    def generate_meds(self):
        meds=pd.read_csv("./data/features/preproc_med_icu.csv.gz", compression='gzip', header=0, index_col=None)
        meds[['start_days', 'dummy','start_hours']] = meds['start_hours_from_admit'].str.split(' ', -1, expand=True)
        meds[['start_hours','min','sec']] = meds['start_hours'].str.split(':', -1, expand=True)
        meds['start_time']=pd.to_numeric(meds['start_days'])*24+pd.to_numeric(meds['start_hours'])
        meds[['start_days', 'dummy','start_hours']] = meds['stop_hours_from_admit'].str.split(' ', -1, expand=True)
        meds[['start_hours','min','sec']] = meds['start_hours'].str.split(':', -1, expand=True)
        meds['stop_time']=pd.to_numeric(meds['start_days'])*24+pd.to_numeric(meds['start_hours'])
        meds=meds.drop(columns=['start_days', 'dummy','start_hours','min','sec'])
        #####Sanity check
        meds['sanity']=meds['stop_time']-meds['start_time']
        meds=meds[meds['sanity']>0]
        del meds['sanity']
        #####Select hadm_id as in main file
        meds=meds[meds['stay_id'].isin(self.data['stay_id'])]
        meds=pd.merge(meds,self.data[['stay_id','los']],on='stay_id',how='left')

        #####Remove where start time is after end of visit
        meds['sanity']=meds['los']-meds['start_time']
        meds=meds[meds['sanity']>0]
        del meds['sanity']
        ####Any stop_time after end of visit is set at end of visit
        meds.loc[meds['stop_time'] > meds['los'],'stop_time']=meds.loc[meds['stop_time'] > meds['los'],'los']
        del meds['los']
        
        meds['rate']=meds['rate'].apply(pd.to_numeric, errors='coerce')
        meds['amount']=meds['amount'].apply(pd.to_numeric, errors='coerce')
        
        self.meds=meds
        
    def generate_ing(self):
        ing=pd.read_csv("./data/features/preproc_ing_icu.csv.gz", compression='gzip', header=0, index_col=None)
        ing[['start_days', 'dummy','start_hours']] = ing['start_hours_from_admit'].str.split(' ', -1, expand=True)
        ing[['start_hours','min','sec']] = ing['start_hours'].str.split(':', -1, expand=True)
        ing['start_time']=pd.to_numeric(ing['start_days'])*24+pd.to_numeric(ing['start_hours'])
        ing[['start_days', 'dummy','start_hours']] = ing['stop_hours_from_admit'].str.split(' ', -1, expand=True)
        ing[['start_hours','min','sec']] = ing['start_hours'].str.split(':', -1, expand=True)
        ing['stop_time']=pd.to_numeric(ing['start_days'])*24+pd.to_numeric(ing['start_hours'])
        ing=ing.drop(columns=['start_days', 'dummy','start_hours','min','sec'])
        #####Sanity check
        ing['sanity']=ing['stop_time']-ing['start_time']
        ing=ing[ing['sanity']>0]
        del ing['sanity']
        #####Select hadm_id as in main file
        ing=ing[ing['stay_id'].isin(self.data['stay_id'])]
        ing=pd.merge(ing,self.data[['stay_id','los']],on='stay_id',how='left')

        #####Remove where start time is after end of visit
        ing['sanity']=ing['los']-ing['start_time']
        ing=ing[ing['sanity']>0]
        del ing['sanity']
        ####Any stop_time after end of visit is set at end of visit
        ing.loc[ing['stop_time'] > ing['los'],'stop_time']=ing.loc[ing['stop_time'] > ing['los'],'los']
        del ing['los']
        
        ing['rate']=ing['rate'].apply(pd.to_numeric, errors='coerce')
        ing['amount']=ing['amount'].apply(pd.to_numeric, errors='coerce')
        
        self.ing=ing
    
    
    def get_stay_id(self):

            
        self.stay = pd.read_csv("./"+"mimiciv/2.2"+"/icu/icustays.csv.gz")
        self.stay = self.stay[self.stay.notna()]
        
        self.chart['charttime'] = pd.to_datetime(self.chart['charttime'])
        self.labs['charttime'] = pd.to_datetime(self.labs['charttime'])

        self.stay['intime'] = pd.to_datetime(self.stay['intime'])
        self.stay['outtime'] = pd.to_datetime(self.stay['outtime'])


        self.labs['stay_id'] = np.nan
        result = []

        unique_patient_ids = self.labs['subject_id'].unique()

        for p in tqdm(range(len(unique_patient_ids))):
            
            p_id = unique_patient_ids[p]
            
            lab = self.labs[self.labs['subject_id']==p_id].copy().sort_values('charttime').reset_index(drop=True)
            stay_interest = self.stay[self.stay['subject_id']==p_id].copy()
            
            unique_stay_ids = stay_interest['stay_id'].unique()
            
            for s in  tqdm(range(len(unique_stay_ids)), leave=False):
                
                stay_id = unique_stay_ids[s]
                
                stay_interest2 = stay_interest[stay_interest['stay_id']==stay_id].copy()
                
                indices = np.where((lab['charttime'].values >= stay_interest2['intime'].values) & 
                                (lab['charttime'].values <= stay_interest2['outtime'].values))

                lab['stay_id'].loc[indices[0]] = stay_id

                result.append(lab)
                
        result_df = pd.concat(result)
        self.labs = result_df[~(result_df['stay_id'].isnull())]
        
   
    def mortality_length(self,include_time,predW):
        include_start_time = 3*24
        include_end_time = 10*24
        print("include start time",include_start_time)
        print("include end time",include_end_time)
        # self.los=include_end_time
        # self.los = self.data['los']
        self.data=self.data[(self.data['los'] >= include_start_time)] #3일
        self.data=self.data[(self.data['los'] <= include_end_time)] #10일
        self.hids=self.data['stay_id'].unique()
        print('num of patient: ', len(self.data))
        print('num of stay: ', len(self.hids))
        print('(MAX)expectation of obsevation: ', len(self.hids)*10*24)
        print('(MIN)expectation of obsevation: ', len(self.hids)*72)
        if(self.feat_cond):
            self.cond=self.cond[self.cond['stay_id'].isin(self.data['stay_id'])]
        
        # self.data['los']=include_time

        ####Make equal length input time series and remove data for pred window if needed
        ####Remove case: 약물 주입의 시작 시간이 los보다 작은 경우 + 약물 주입의 끝 시간이 los 보다 클 경우
        ####Lab은 stay id가 부여되고 들어가야함
        
        ###MEDS
        if(self.feat_med):
            self.meds=self.meds[self.meds['stay_id'].isin(self.data['stay_id'])]
            self.meds=self.meds[self.meds['start_time'] <= include_end_time]
            self.meds.loc[self.meds.stop_time > include_end_time, 'stop_time']=include_end_time
            
        ###ING
        if(self.feat_ing):
            self.ing=self.ing[self.ing['stay_id'].isin(self.data['stay_id'])]
            self.ing=self.ing[self.ing['start_time'] <= include_end_time]
            self.ing.loc[self.ing.stop_time > include_end_time, 'stop_time']=include_end_time
                    
        
        ###PROCS
        if(self.feat_proc):
            self.proc=self.proc[self.proc['stay_id'].isin(self.data['stay_id'])]
            self.proc=self.proc[self.proc['start_time']<=include_end_time]
            
        ###OUT
        if(self.feat_out):
            self.out=self.out[self.out['stay_id'].isin(self.data['stay_id'])]
            self.out=self.out[self.out['start_time']<=include_end_time]
            
       ###CHART
        if(self.feat_chart):
            self.chart=self.chart[self.chart['stay_id'].isin(self.data['stay_id'])]
            self.chart=self.chart[self.chart['start_time']<=include_end_time]
            
        ###LAB
        if(self.feat_lab):
            self.labs=self.labs[self.labs['stay_id'].isin(self.data['stay_id'])]
            self.labs=self.labs[self.labs['start_time']<=include_end_time]
        
        #self.los=include_time
    def los_length(self,include_time):
        print("include_time",include_time)
        self.los=include_time
        self.data=self.data[(self.data['los']>=include_time)]
        self.hids=self.data['stay_id'].unique()
        
        if(self.feat_cond):
            self.cond=self.cond[self.cond['stay_id'].isin(self.data['stay_id'])]
        
        self.data['los']=include_time

        ####Make equal length input time series and remove data for pred window if needed
        
        ###MEDS
        if(self.feat_med):
            self.meds=self.meds[self.meds['stay_id'].isin(self.data['stay_id'])]
            self.meds=self.meds[self.meds['start_time']<=include_time]
            self.meds.loc[self.meds.stop_time >include_time, 'stop_time']=include_time

        ###ING
        if(self.feat_ing):
            self.ing=self.ing[self.ing['stay_id'].isin(self.data['stay_id'])]
            self.ing=self.ing[self.ing['start_time']<=include_time]
            self.ing.loc[self.ing.stop_time >include_time, 'stop_time']=include_time
                    
        
        ###PROCS
        if(self.feat_proc):
            self.proc=self.proc[self.proc['stay_id'].isin(self.data['stay_id'])]
            self.proc=self.proc[self.proc['start_time']<=include_time]
            
        ###OUT
        if(self.feat_out):
            self.out=self.out[self.out['stay_id'].isin(self.data['stay_id'])]
            self.out=self.out[self.out['start_time']<=include_time]
            
       ###CHART
        if(self.feat_chart):
            self.chart=self.chart[self.chart['stay_id'].isin(self.data['stay_id'])]
            self.chart=self.chart[self.chart['start_time']<=include_time]
            
        ###LAB
        if(self.feat_lab):
            self.labs=self.labs[self.labs['stay_id'].isin(self.data['stay_id'])]
            self.labs=self.labs[self.labs['start_time']<=include_time]
            
    def readmission_length(self,include_time):
        self.los=include_time
        self.data=self.data[(self.data['los']>=include_time)]
        self.hids=self.data['stay_id'].unique()
        
        if(self.feat_cond):
            self.cond=self.cond[self.cond['stay_id'].isin(self.data['stay_id'])]
        self.data['select_time']=self.data['los']-include_time
        self.data['los']=include_time

        ####Make equal length input time series and remove data for pred window if needed
        
        ###MEDS
        if(self.feat_med):
            self.meds=self.meds[self.meds['stay_id'].isin(self.data['stay_id'])]
            self.meds=pd.merge(self.meds,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.meds['stop_time']=self.meds['stop_time']-self.meds['select_time']
            self.meds['start_time']=self.meds['start_time']-self.meds['select_time']
            self.meds=self.meds[self.meds['stop_time']>=0]
            self.meds.loc[self.meds.start_time <0, 'start_time']=0
            
        ###INGS
        if(self.feat_ing):
            self.ing=self.ing[self.ing['stay_id'].isin(self.data['stay_id'])]
            self.ing=pd.merge(self.ing,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.ing['stop_time']=self.ing['stop_time']-self.ing['select_time']
            self.ing['start_time']=self.ing['start_time']-self.ing['select_time']
            self.ing=self.ing[self.ing['stop_time']>=0]
            self.ing.loc[self.ing.start_time <0, 'start_time']=0
        
        ###PROCS
        if(self.feat_proc):
            self.proc=self.proc[self.proc['stay_id'].isin(self.data['stay_id'])]
            self.proc=pd.merge(self.proc,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.proc['start_time']=self.proc['start_time']-self.proc['select_time']
            self.proc=self.proc[self.proc['start_time']>=0]
            
        ###OUT
        if(self.feat_out):
            self.out=self.out[self.out['stay_id'].isin(self.data['stay_id'])]
            self.out=pd.merge(self.out,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.out['start_time']=self.out['start_time']-self.out['select_time']
            self.out=self.out[self.out['start_time']>=0]
            
       ###CHART
        if(self.feat_chart):
            self.chart=self.chart[self.chart['stay_id'].isin(self.data['stay_id'])]
            self.chart=pd.merge(self.chart,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.chart['start_time']=self.chart['start_time']-self.chart['select_time']
            self.chart=self.chart[self.chart['start_time']>=0]

        ###LAB
        if(self.feat_lab):
            self.labs=self.labs[self.labs['stay_id'].isin(self.data['stay_id'])]
            self.labs=self.labs[self.labs['start_time']<=include_time]
            self.labs=pd.merge(self.labs,self.data[['stay_id','select_time']],on='stay_id',how='left')
            self.labs['start_time']=self.labs['start_time']-self.labs['select_time']
            self.labs=self.labs[self.labs['start_time']>=0]
        
            
    def smooth_meds(self,bucket):
        final_meds=pd.DataFrame()
        final_ing=pd.DataFrame()
        final_proc=pd.DataFrame()
        final_out=pd.DataFrame()
        final_chart=pd.DataFrame()
        final_labs=pd.DataFrame()
        
        if(self.feat_med):
            self.meds=self.meds.sort_values(by=['start_time'])
        if(self.feat_ing):
            self.ing=self.ing.sort_values(by=['start_time'])
        if(self.feat_proc):
            self.proc=self.proc.sort_values(by=['start_time'])
        if(self.feat_out):
            self.out=self.out.sort_values(by=['start_time'])
        if(self.feat_chart):
            self.chart=self.chart.sort_values(by=['start_time'])
        if(self.feat_lab):
            self.labs=self.labs.sort_values(by=['start_time'])
            
        sample_data = pd.concat([self.chart[['stay_id', 'itemid']], self.labs[['stay_id', 'itemid']]], axis = 0)
        # Specify the item_ids we are interested in
        required_item_ids = {225668, 50813, 220045, 220739, 223900, 223901, 223835, 220224}

        # Find the stay_ids that have all the required item_ids at least once
        valid_stay_ids = sample_data[sample_data['itemid'].isin(required_item_ids)].groupby('stay_id')['itemid'].nunique()
        valid_stay_ids = valid_stay_ids[valid_stay_ids == len(required_item_ids)].index
        
        self.meds = self.meds[self.meds['stay_id'].isin(valid_stay_ids)]
        self.ing = self.ing[self.ing['stay_id'].isin(valid_stay_ids)]
        self.proc = self.proc[self.proc['stay_id'].isin(valid_stay_ids)]
        self.out = self.out[self.out['stay_id'].isin(valid_stay_ids)]
        self.chart = self.chart[self.chart['stay_id'].isin(valid_stay_ids)]
        self.labs = self.labs[self.labs['stay_id'].isin(valid_stay_ids)]
        self.data = self.data[self.data['stay_id'].isin(valid_stay_ids)]

        print('Number of stay: ', len(self.data.stay_id.unique()))
        print('expected observation with time resample 1 hour: ', self.data['los'].sum())
        
        for data_type in ['meds', 'ing', 'proc', 'out', 'chart', 'labs']:
            print(data_type)
            if data_type == "meds":
                df = meds.copy()
            elif data_type == "ing":
                df = ing.copy()
            elif data_type == "proc":
                df = proc.copy()
            elif data_type == "out":
                df = out.copy()
            elif data_type == "chart":
                df = chart.copy()
            elif data_type == "labs":
                df = labs.copy()
                
            for hid in tqdm(valid_stay_ids, desc = f'Total stay with Processing {data_type}'):
                grp = data[data['stay_id']==hid]
                los = int(grp['los'].values[0])
                df = df[df['stay_id']==hid]
                t = 0
                for i in np.arange(0, los, bucket):
                    if data_type == "meds" or data_type == "ing":
                        sub_df = df[(df['start_time'] >= i) & (df['start_time'] < i + bucket)].groupby(['stay_id', 'itemid', 'orderid']).agg({'stop_time': 'max', 'subject_id': 'max', 'rate': np.nanmean, 'amount': np.nanmean}).reset_index()
                        sub_df['stop_time'] /= bucket
                        sub_df['start_time']=t
                    elif data_type == "proc":
                        sub_df = df[(df['start_time'] >= i) & (df['start_time'] < i + bucket)].groupby(['stay_id', 'itemid']).agg({'subject_id': 'max'}).reset_index()
                        sub_df['start_time']=t
                    elif data_type == "out" or data_type == "chart" or data_type == "labs":
                        value_column = 'value' if data_type == 'out' else 'valuenum'
                        sub_df = df[(df['start_time'] >= i) & (df['start_time'] < i + bucket)].groupby(['stay_id', 'itemid']).agg({value_column: np.nanmean}).reset_index()
                        sub_df['start_time']=t
                    
                    if data_type == 'meds':
                        if final_meds.empty:
                                final_meds=sub_df
                        else:    
                            final_meds=final_meds.append(sub_df) 
                    elif data_type == 'ing':
                        if final_ing.empty:
                                final_ing=sub_df
                        else:    
                            final_ing=final_ing.append(sub_df) 
                    elif data_type == 'proc':
                        if final_proc.empty:
                                final_proc=sub_df
                        else:    
                            final_proc=final_proc.append(sub_df) 
                    elif data_type == 'out':
                        if final_out.empty:
                                final_out=sub_df
                        else:    
                            final_out=final_out.append(sub_df) 
                    elif data_type == 'chart':
                        if final_chart.empty:
                                final_chart=sub_df
                        else:    
                            final_chart=final_chart.append(sub_df) 
                    elif data_type == 'labs':
                        if final_labs.empty:
                                final_labs=sub_df
                        else:    
                            final_labs=final_labs.append(sub_df) 
                    t = t+1       

                
        # print("bucket",bucket)
        # los=int(self.los/bucket)
        
        ###MEDS
        if(self.feat_med):
            f2_meds=final_meds.groupby(['stay_id','itemid','orderid']).size()
            self.med_per_adm=f2_meds.groupby('stay_id').sum().reset_index()[0].max()                 
            self.medlength_per_adm=final_meds.groupby('stay_id').size().max()

        ###INGS
        if(self.feat_ing):
            f2_ing=final_ing.groupby(['stay_id','itemid','orderid']).size()
            self.med_per_adm=f2_ing.groupby('stay_id').sum().reset_index()[0].max()                 
            self.medlength_per_adm=final_ing.groupby('stay_id').size().max()
        
        ###PROC
        if(self.feat_proc):
            f2_proc=final_proc.groupby(['stay_id','itemid']).size()
            self.proc_per_adm=f2_proc.groupby('stay_id').sum().reset_index()[0].max()       
            self.proclength_per_adm=final_proc.groupby('stay_id').size().max()
            
        ###OUT
        if(self.feat_out):
            f2_out=final_out.groupby(['stay_id','itemid']).size()
            self.out_per_adm=f2_out.groupby('stay_id').sum().reset_index()[0].max() 
            self.outlength_per_adm=final_out.groupby('stay_id').size().max()
            
            
        ###chart
        if(self.feat_chart):
            f2_chart=final_chart.groupby(['stay_id','itemid']).size()
            self.chart_per_adm=f2_chart.groupby('stay_id').sum().reset_index()[0].max()             
            self.chartlength_per_adm=final_chart.groupby('stay_id').size().max()
            
       ###LABS
        if(self.feat_lab):
            f2_labs=final_labs.groupby(['stay_id','itemid']).size()
            self.labs_per_adm=f2_labs.groupby('stay_id').sum().reset_index()[0].max()        
            self.labslength_per_adm=final_labs.groupby('stay_id').size().max()
        
        print("[ PROCESSED TIME SERIES TO EQUAL TIME INTERVAL ]")
        ###CREATE DICT
#         if(self.feat_chart):
#             self.create_chartDict(final_chart,los)
#         else:
        self.create_Dict(final_meds,final_proc,final_out,final_chart,final_labs,final_ing)# , los   
            
    def create_Dict(self,meds,proc,out,chart,labs,ing): # ,los
        dataDic={}
        # print(los)
        labels_csv=pd.DataFrame(columns=['stay_id','label'])
        labels_csv['stay_id']=pd.Series(self.hids)
        labels_csv['label']=0
#         print("# Unique gender",self.data.gender.nunique())
#         print("# Unique ethnicity",self.data.ethnicity.nunique())
#         print("# Unique insurance",self.data.insurance.nunique())

        for hid in tqdm(self.hids):
            grp=self.data[self.data['stay_id']==hid]
            dataDic[hid]={'Cond':{},'Proc':{},'Med':{},'Ing':{},'Out':{},'Chart':{},'Lab':{},'ethnicity':grp['ethnicity'].iloc[0],'age':int(grp['Age']),'gender':grp['gender'].iloc[0],'label':int(grp['label'])}
            labels_csv.loc[labels_csv['stay_id']==hid,'label']=int(grp['label'])
            
            los = int(grp['los'].values)
           
            demo_csv=grp[['Age','gender','ethnicity','insurance']]
            
            if not os.path.exists("./data/csv/"+str(hid)):
                os.makedirs("./data/csv/"+str(hid))
            demo_csv.to_csv('./data/csv/'+str(hid)+'/demo.csv',index=False)
            
            dyn_csv=pd.DataFrame()
            ###MEDS
            if(self.feat_med):
                feat=meds['itemid'].unique()
                df2=meds[meds['stay_id']==hid]
                if df2.shape[0]==0:
                    amount=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    amount=amount.fillna(0)
                    amount.columns=pd.MultiIndex.from_product([["MEDS"], amount.columns])
                else:
                    rate=df2.pivot_table(index='start_time',columns='itemid',values='rate')
                    #print(rate)
                    amount=df2.pivot_table(index='start_time',columns='itemid',values='amount')
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='stop_time')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.ffill()
                    df2=df2.fillna(0)

                    rate=pd.concat([rate, add_df])
                    rate=rate.sort_index()
                    rate=rate.ffill()
                    rate=rate.fillna(-1)

                    amount=pd.concat([amount, add_df])
                    amount=amount.sort_index()
                    amount=amount.ffill()
                    amount=amount.fillna(-1)
                    #print(df2.head())
                    df2.iloc[:,0:]=df2.iloc[:,0:].sub(df2.index,0)
                    df2[df2>0]=1
                    df2[df2<0]=0
                    rate.iloc[:,0:]=df2.iloc[:,0:]*rate.iloc[:,0:]
                    amount.iloc[:,0:]=df2.iloc[:,0:]*amount.iloc[:,0:]
                    #print(df2.head())
                    dataDic[hid]['Med']['signal']=df2.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Med']['rate']=rate.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Med']['amount']=amount.iloc[:,0:].to_dict(orient="list")


                    feat_df=pd.DataFrame(columns=list(set(feat)-set(amount.columns)))
                    feat_df_rate = pd.DataFrame(columns=list(set(feat)-set(rate.columns)))
    #                 print(feat)
    #                 print(amount.columns)
    #                 print(amount.head())
                    amount=pd.concat([amount,feat_df],axis=1)
                    rate=pd.concat([rate,feat_df_rate],axis=1)

                    amount=amount[feat]
                    amount=amount.fillna(0)
                    rate=rate[feat]
                    rate=rate.fillna(0)
    #                 print(amount.columns)
                    amount.columns=pd.MultiIndex.from_product([["MEDS"], amount.columns])
                    rate.columns=pd.MultiIndex.from_product([["MEDS Rate"], rate.columns])

                    medication = pd.concat([amount, rate], axis = 1)
                    
                if(dyn_csv.empty):
                    dyn_csv=medication
                else:
                    dyn_csv=pd.concat([dyn_csv,medication],axis=1)
                
           
            ###INGS
            if(self.feat_ing):
                feat=ing['itemid'].unique()
                df2=ing[ing['stay_id']==hid]
                if df2.shape[0]==0:
                    amount=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    amount=amount.fillna(0)
                    amount.columns=pd.MultiIndex.from_product([["INGS"], amount.columns])
                else:
                    rate=df2.pivot_table(index='start_time',columns='itemid',values='rate')
                    #print(rate)
                    amount=df2.pivot_table(index='start_time',columns='itemid',values='amount')
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='stop_time')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.ffill()
                    df2=df2.fillna(0)

                    rate=pd.concat([rate, add_df])
                    rate=rate.sort_index()
                    rate=rate.ffill()
                    rate=rate.fillna(-1)

                    amount=pd.concat([amount, add_df])
                    amount=amount.sort_index()
                    amount=amount.ffill()
                    amount=amount.fillna(-1)
                    #print(df2.head())
                    df2.iloc[:,0:]=df2.iloc[:,0:].sub(df2.index,0)
                    df2[df2>0]=1
                    df2[df2<0]=0
                    rate.iloc[:,0:]=df2.iloc[:,0:]*rate.iloc[:,0:]
                    amount.iloc[:,0:]=df2.iloc[:,0:]*amount.iloc[:,0:]
                    #print(df2.head())
                    dataDic[hid]['Ing']['signal']=df2.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Ing']['rate']=rate.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Ing']['amount']=amount.iloc[:,0:].to_dict(orient="list")


                    feat_df=pd.DataFrame(columns=list(set(feat)-set(amount.columns)))
                    feat_df_rate = pd.DataFrame(columns=list(set(feat)-set(rate.columns)))
    #                 print(feat)
    #                 print(amount.columns)
    #                 print(amount.head())
                    amount=pd.concat([amount,feat_df],axis=1)
                    rate=pd.concat([rate,feat_df_rate],axis=1)

                    amount=amount[feat]
                    amount=amount.fillna(0)
                    rate=rate[feat]
                    rate=rate.fillna(0)
    #                 print(amount.columns)
                    amount.columns=pd.MultiIndex.from_product([["INGS"], amount.columns])
                    rate.columns=pd.MultiIndex.from_product([["INGS Rate"], rate.columns])

                    ingredients = pd.concat([amount, rate], axis = 1)
                    
                if(dyn_csv.empty):
                    dyn_csv=medication
                else:
                    dyn_csv=pd.concat([dyn_csv,medication],axis=1)
                
                
            
            
            ###PROCS
            if(self.feat_proc):
                feat=proc['itemid'].unique()
                df2=proc[proc['stay_id']==hid]
                if df2.shape[0]==0:
                    df2=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    df2=df2.fillna(0)
                    df2.columns=pd.MultiIndex.from_product([["PROC"], df2.columns])
                else:
                    df2['val']=1
                    #print(df2)
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='val')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.fillna(0)
                    df2[df2>0]=1
                    #print(df2.head())
                    dataDic[hid]['Proc']=df2.to_dict(orient="list")


                    feat_df=pd.DataFrame(columns=list(set(feat)-set(df2.columns)))
                    df2=pd.concat([df2,feat_df],axis=1)

                    df2=df2[feat]
                    df2=df2.fillna(0)
                    df2.columns=pd.MultiIndex.from_product([["PROC"], df2.columns])
                
                if(dyn_csv.empty):
                    dyn_csv=df2
                else:
                    dyn_csv=pd.concat([dyn_csv,df2],axis=1)
                
                
                
                   
            ###OUT
            if(self.feat_out):
                feat=out['itemid'].unique()
                df2=out[out['stay_id']==hid]
            
                if df2.shape[0]==0:
                    val=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["OUT"], val.columns])
                else:
                    val=df2.pivot_table(index='start_time',columns='itemid',values='value')
                    df2['val']=1
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='val')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.fillna(0)

                    val=pd.concat([val, add_df])
                    val=val.sort_index()
                    val=val.fillna(0)
                    
                    df2[df2>0]=1
                    df2[df2<0]=0
                    #print(df2.head())
                    
                    dataDic[hid]['Out']['signal']=df2.iloc[:,0:].to_dict(orient="list") #값이 있으면 1 아니면 0
                    dataDic[hid]['Out']['val']=val.iloc[:,0:].to_dict(orient="list")

                    feat_df=pd.DataFrame(columns=list(set(feat)-set(val.columns)))
                    val=pd.concat([val,feat_df],axis=1)

                    val=val[feat]
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["OUT"], val.columns])
                
                if(dyn_csv.empty):
                    dyn_csv=val
                else:
                    dyn_csv=pd.concat([dyn_csv,val],axis=1)
                    
                
            ###CHART
            if(self.feat_chart):
                feat=chart['itemid'].unique()
                df2=chart[chart['stay_id']==hid]
                if df2.shape[0]==0:
                    val=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["CHART"], val.columns])
                else:
                    val=df2.pivot_table(index='start_time',columns='itemid',values='valuenum')
                    df2['val']=1
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='val')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.fillna(0)

                    val=pd.concat([val, add_df])
                    val=val.sort_index()
                    if self.impute=='Mean':
                        val=val.ffill()
                        val=val.bfill()
                        val=val.interpolate()
                    elif self.impute=='Median':
                        val=val.ffill()
                        val=val.bfill()
                        val=val.interpolate()
                    val=val.fillna(0)


                    df2[df2>0]=1
                    df2[df2<0]=0
                    #print(df2.head())
                    dataDic[hid]['Chart']['signal']=df2.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Chart']['val']=val.iloc[:,0:].to_dict(orient="list")

                    feat_df=pd.DataFrame(columns=list(set(feat)-set(val.columns)))
                    val=pd.concat([val,feat_df],axis=1)

                    val=val[feat]
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["CHART"], val.columns])
                
                if(dyn_csv.empty):
                    dyn_csv=val
                else:
                    dyn_csv=pd.concat([dyn_csv,val],axis=1)
            
            # #Save temporal data to csv
            # dyn_csv.to_csv('./data/csv/'+str(hid)+'/dynamic.csv',index=False)
            
            ###LABS
            if(self.feat_lab):
                feat=labs['itemid'].unique()
                df2=labs[labs['stay_id']==hid]
                if df2.shape[0]==0:
                    val=pd.DataFrame(np.zeros([los,len(feat)]),columns=feat)
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["LAB"], val.columns])
                else:
                    val=df2.pivot_table(index='start_time',columns='itemid',values='valuenum')
                    df2['val']=1
                    df2=df2.pivot_table(index='start_time',columns='itemid',values='val')
                    #print(df2.shape)
                    add_indices = pd.Index(range(los)).difference(df2.index)
                    add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(np.nan)
                    df2=pd.concat([df2, add_df])
                    df2=df2.sort_index()
                    df2=df2.fillna(0)

                    val=pd.concat([val, add_df])
                    val=val.sort_index()
                    if self.impute=='Mean':
                        val=val.ffill()
                        val=val.bfill()
                        val=val.fillna(val.mean())
                    elif self.impute=='Median':
                        val=val.ffill()
                        val=val.bfill()
                        val=val.fillna(val.median())
                    val=val.fillna(0)

                    df2[df2>0]=1
                    df2[df2<0]=0

                    #print(df2.head())
                    dataDic[hid]['Lab']['signal']=df2.iloc[:,0:].to_dict(orient="list")
                    dataDic[hid]['Lab']['val']=val.iloc[:,0:].to_dict(orient="list")
                    
                    feat_df=pd.DataFrame(columns=list(set(feat)-set(val.columns)))
                    val=pd.concat([val,feat_df],axis=1)

                    val=val[feat]
                    val=val.fillna(0)
                    val.columns=pd.MultiIndex.from_product([["LAB"], val.columns])
                
                if(dyn_csv.empty):
                    dyn_csv=val
                else:
                    dyn_csv=pd.concat([dyn_csv,val],axis=1)
            
            #Save temporal data to csv
            dyn_csv.to_csv('./data/csv/'+str(hid)+'/dynamic.csv',index=False)
            
            
            ##########COND#########
            if(self.feat_cond):
                feat=self.cond['new_icd_code'].unique()
                grp=self.cond[self.cond['stay_id']==hid]
                if(grp.shape[0]==0):
                    dataDic[hid]['Cond']={'fids':list(['<PAD>'])}
                    feat_df=pd.DataFrame(np.zeros([1,len(feat)]),columns=feat)
                    grp=feat_df.fillna(0)
                    grp.columns=pd.MultiIndex.from_product([["COND"], grp.columns])
                else:
                    dataDic[hid]['Cond']={'fids':list(grp['new_icd_code'])}
                    grp['val']=1
                    grp=grp.drop_duplicates()
                    grp=grp.pivot(index='stay_id',columns='new_icd_code',values='val').reset_index(drop=True)
                    feat_df=pd.DataFrame(columns=list(set(feat)-set(grp.columns)))
                    grp=pd.concat([grp,feat_df],axis=1)
                    grp=grp.fillna(0)
                    grp=grp[feat]
                    grp.columns=pd.MultiIndex.from_product([["COND"], grp.columns])
            grp.to_csv('./data/csv/'+str(hid)+'/static.csv',index=False)   
            labels_csv.to_csv('./data/csv/labels.csv',index=False)    
            
                
        ######SAVE DICTIONARIES##############
        metaDic={'Cond':{},'Proc':{},'Med':{},'Ing':{},'Out':{},'Chart':{},'Lab':{}} #,'LOS':{}
        # metaDic['LOS']=los
        with open("./data/dict/dataDic", 'wb') as fp:
            pickle.dump(dataDic, fp)

        with open("./data/dict/hadmDic", 'wb') as fp:
            pickle.dump(self.hids, fp)
        
        with open("./data/dict/ethVocab", 'wb') as fp:
            pickle.dump(list(self.data['ethnicity'].unique()), fp)
            self.eth_vocab = self.data['ethnicity'].nunique()
            
        with open("./data/dict/ageVocab", 'wb') as fp:
            pickle.dump(list(self.data['Age'].unique()), fp)
            self.age_vocab = self.data['Age'].nunique()
            
        with open("./data/dict/insVocab", 'wb') as fp:
            pickle.dump(list(self.data['insurance'].unique()), fp)
            self.ins_vocab = self.data['insurance'].nunique()
            
        if(self.feat_med):
            with open("./data/dict/medVocab", 'wb') as fp:
                pickle.dump(list(meds['itemid'].unique()), fp)
            self.med_vocab = meds['itemid'].nunique()
            metaDic['Med']=self.med_per_adm
            
        if(self.feat_ing):
            with open("./data/dict/medVocab", 'wb') as fp:
                pickle.dump(list(ing['itemid'].unique()), fp)
            self.med_vocab = ing['itemid'].nunique()
            metaDic['Ing']=self.med_per_adm
            
        if(self.feat_out):
            with open("./data/dict/outVocab", 'wb') as fp:
                pickle.dump(list(out['itemid'].unique()), fp)
            self.out_vocab = out['itemid'].nunique()
            metaDic['Out']=self.out_per_adm
            
        if(self.feat_chart):
            with open("./data/dict/chartVocab", 'wb') as fp:
                pickle.dump(list(chart['itemid'].unique()), fp)
            self.chart_vocab = chart['itemid'].nunique()
            metaDic['Chart']=self.chart_per_adm
        
        if(self.feat_cond):
            with open("./data/dict/condVocab", 'wb') as fp:
                pickle.dump(list(self.cond['new_icd_code'].unique()), fp)
            self.cond_vocab = self.cond['new_icd_code'].nunique()
            metaDic['Cond']=self.cond_per_adm
        
        if(self.feat_proc):    
            with open("./data/dict/procVocab", 'wb') as fp:
                pickle.dump(list(proc['itemid'].unique()), fp)
            self.proc_vocab = proc['itemid'].nunique()
            metaDic['Proc']=self.proc_per_adm
            
        if(self.feat_lab):    
            with open("./data/dict/labsVocab", 'wb') as fp:
                pickle.dump(list(labs['itemid'].unique()), fp)
            self.lab_vocab = labs['itemid'].unique()
            metaDic['Lab']=self.labs_per_adm        
            
        with open("./data/dict/metaDic", 'wb') as fp:
            pickle.dump(metaDic, fp)
            
            
      


