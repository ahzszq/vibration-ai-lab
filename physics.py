import math
import numpy as np

DEFAULTS = {'Omegaet': 1.0, 'Omegaeh': 1.0, 'Phih': 0.0, 'Phit': 0.0, 'Epsilon11': 0.01, 'Epsilon13': 0.0125, 'Epsilon22': 0.01, 'Epsilon23': 0.0125, 'Epsilon33': 0.02, 'K11': 1.25, 'K13': 0.25, 'K22': 1.25, 'K23': 0.25, 'Ffb': 0.0, 'Ffp': 0.0, 'Ffm': 0.1, 'Fat': 0.0, 'Fah': 0.05, 'HG': 1.3, 'Hb1': 1.0, 'Hb2': 1.0, 'NT_total': 20000, 'NT_start': 12000, 'NN': 256}

class Solver:
    def F(self, Y, T, params):
            """计算导数"""
            if Y[4] > params['HG']:
                FM = Y[4] - params['HG']
            elif Y[4] < -params['HG']:
                FM = Y[4] + params['HG']
            else:
                FM = 0.0
            
            if Y[0] > params['Hb1']:
                FP = Y[0] - params['Hb1']
            elif Y[0] < -params['Hb1']:
                FP = Y[0] + params['Hb1']
            else:
                FP = 0.0
            
            if Y[2] > params['Hb2']:
                FG = Y[2] - params['Hb2']
            elif Y[2] < -params['Hb2']:
                FG = Y[2] + params['Hb2']
            else:
                FG = 0.0
            
            YPRIME = [0.0] * 6
            YPRIME[0] = Y[1]
            YPRIME[1] = (-2.0 * params['Epsilon11'] * Y[1] + 
                         2.0 * params['Epsilon13'] * Y[5] - 
                         params['K11'] * FP + params['K13'] * FM - params['Ffp'])
            YPRIME[2] = Y[3]
            YPRIME[3] = (-2.0 * params['Epsilon22'] * Y[3] - 
                         2.0 * params['Epsilon23'] * Y[5] - 
                         params['K22'] * FG - params['K23'] * FM + params['Ffb'])
            YPRIME[4] = Y[5]
            YPRIME[5] = (-2.0 * params['Epsilon33'] * Y[5] - FM + 
                         params['Fah'] * params['Omegaeh']**2 * math.sin(params['Omegaeh'] * T + params['Phih']) + 
                         params['Ffm'] + params['Fat'] * math.sin(params['Omegaet'] * T + params['Phit']) - 
                         YPRIME[1] + YPRIME[3])
            return YPRIME

    def RK4(self, Y, T, DT, params):
            """四阶龙格-库塔"""
            N = 6
            SQT2 = math.sqrt(2.0)
            U1 = [0.0] * N
            U2 = [0.0] * N
            U3 = [0.0] * N
            U4 = [0.0] * N
            YY = [0.0] * N
            
            for i in range(N):
                YY[i] = Y[i]
            
            YPRIME = self.F(YY, T, params)
            for i in range(N):
                U1[i] = DT * YPRIME[i]
            
            for i in range(N):
                YY[i] = Y[i] + 0.5 * U1[i]
            YPRIME = self.F(YY, T + 0.5 * DT, params)
            for i in range(N):
                U2[i] = DT * YPRIME[i]
            
            for i in range(N):
                YY[i] = Y[i] + 0.5 * U1[i] * (SQT2 - 1.0) + (1.0 - 0.5 * SQT2) * U2[i]
            YPRIME = self.F(YY, T + 0.5 * DT, params)
            for i in range(N):
                U3[i] = DT * YPRIME[i]
            
            for i in range(N):
                U3[i] = DT * YPRIME[i]
                YY[i] = Y[i] + (1.0 + 0.5 * SQT2) * U3[i] - 0.5 * SQT2 * U2[i]
            
            YPRIME = self.F(YY, T + DT, params)
            for i in range(N):
                U4[i] = DT * YPRIME[i]
            
            for i in range(N):
                Y[i] = Y[i] + (U1[i] + (2.0 - SQT2) * U2[i] + (2.0 + SQT2) * U3[i] + U4[i]) / 6.0
            
            return Y
