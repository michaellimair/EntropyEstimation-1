#!/usr/bin/env python
# coding: utf-8

# In[2]:


from pytorchtools import EarlyStopping
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.autograd as autograd

class Mine(nn.Module):
    def __init__(self, input_size=2, hidden_size=100):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, 1)
        nn.init.normal_(self.fc1.weight,std=0.02)
        nn.init.constant_(self.fc1.bias, 0)
        nn.init.normal_(self.fc2.weight,std=0.02)
        nn.init.constant_(self.fc2.bias, 0)
        nn.init.normal_(self.fc3.weight,std=0.02)
        nn.init.constant_(self.fc3.bias, 0)
        
    def forward(self, input):
        output = F.elu(self.fc1(input))
        output = F.elu(self.fc2(output))
        output = self.fc3(output)
        return output

def mutual_information(joint, marginal, mine_net):
    t = mine_net(joint)
    et = torch.exp(mine_net(marginal))
    mi_lb = torch.mean(t) - torch.log(torch.mean(et))
    return mi_lb, t, et

def learn_mine(batch, mine_net, mine_net_optim,  ma_et, ma_rate=0.01):
    # batch is a tuple of (joint, marginal)
    joint , marginal = batch
    joint = torch.autograd.Variable(torch.FloatTensor(joint))
    marginal = torch.autograd.Variable(torch.FloatTensor(marginal))
    mi_lb , t, et = mutual_information(joint, marginal, mine_net)
    ma_et = (1-ma_rate)*ma_et + ma_rate*torch.mean(et)
    
    # unbiasing use moving average
    loss = -(torch.mean(t) - (1/ma_et.mean()).detach()*torch.mean(et))
    # use biased estimator
#     loss = - mi_lb
    
    mine_net_optim.zero_grad()
    autograd.backward(loss)
    mine_net_optim.step()
    return mi_lb, ma_et

def valid_mine(batch, mine_net):
    joint , marginal = batch
    joint = torch.autograd.Variable(torch.FloatTensor(joint))
    marginal = torch.autograd.Variable(torch.FloatTensor(marginal))
    mi_lb , t, et = mutual_information(joint, marginal, mine_net)
    return mi_lb
    

def create_dataset(data, batch_size=100):
    if data.shape[0] >= batch_size * 2:
        partSize = int(data.shape[0]/2)
        indices = list(range(data.shape[0]))
        np.random.shuffle(indices)
        valid_idx = indices[:partSize]
        train_idx = indices[partSize:]
        train_data = data[train_idx]
        valid_data = data[valid_idx]
        return train_data, valid_data
    
def sample_batch(data, resp, cond, batch_size=100, sample_mode='joint'):
#     if sample_mode == 'joint':
#         index = np.random.choice(range(data.shape[0]), size=batch_size, replace=False)
#         batch = data[index]
#     else:
#         joint_index = np.random.choice(range(data.shape[0]), size=batch_size, replace=False)
#         marginal_index = np.random.choice(range(data.shape[0]), size=batch_size, replace=False)
#         batch = np.concatenate([data[joint_index][:,0].reshape(-1,1),
#                                          data[marginal_index][:,1].reshape(-1,1)],
#                                        axis=1)
    index = np.random.choice(range(data.shape[0]), size=batch_size, replace=False)
    batch_joint = data[index]
    marginal_index = np.random.choice(range(batch_joint.shape[0]), size=batch_size, replace=False)
    
#     print (batch_joint[:,0].reshape(-1,1).shape)
#     print (batch_joint[marginal_index][:,[1,2]].reshape(-1,2).shape)
    if data.shape[1] == 2:
        batch_mar = np.concatenate([batch_joint[:,0].reshape(-1,1),
                                     batch_joint[marginal_index][:,1].reshape(-1,1)],
                                   axis=1)
    else:
        batch_mar = np.concatenate([batch_joint[:,resp].reshape(-1,1),
                                     batch_joint[marginal_index][:,cond].reshape(-1,data.shape[1]-1)],
                                   axis=1)
    return batch_joint, batch_mar

def train(data, mine_net,mine_net_optim, resp=0, cond=1, batch_size=100          , iter_num=int(1e+4), log_freq=int(1e+3)          , avg_freq=int(1e+2), verbose=True, patience=20):
    # data is x or y
    result = list()
    ma_et = 1.
    
    #Early Stopping
    train_losses = []
    valid_losses = []
    avg_train_losses = []
    avg_valid_losses = []
    
    earlyStop = EarlyStopping(patience=patience, verbose=True)
    trainData, validData = create_dataset(data, batch_size)
    for i in range(iter_num):
        #get train data
        batchTrain = sample_batch(trainData,resp, cond, batch_size=batch_size)
        mi_lb, ma_et = learn_mine(batchTrain, mine_net, mine_net_optim, ma_et)
        result.append(mi_lb.detach().cpu().numpy())
        train_losses.append(result[-1].item())
        if verbose and (i+1)%(log_freq)==0:
            print(result[-1])
        
        batchValid = sample_batch(validData,resp, cond, batch_size=batch_size)
        mi_lb_valid = valid_mine(batchValid, mine_net)
        valid_losses.append(mi_lb_valid.item())
        
        if (i+1)%(avg_freq)==0:
            train_loss = np.average(train_losses)
            valid_loss = np.average(valid_losses)
            avg_train_losses.append(train_loss)
            avg_valid_losses.append(valid_loss)

            print_msg = "[{0}/{1}] train_loss: {2} valid_loss: {3}".format(i, iter_num, train_loss, valid_loss)
            print (print_msg)

            train_losses = []
            valid_losses = []

            earlyStop(valid_loss, mine_net)
            if (earlyStop.early_stop):
                print("Early stopping")
                break
            
    mine_net.load_state_dict(torch.load('checkpoint.pt'))
    return mine_net, avg_train_losses, avg_valid_losses

def ma(a, window_size=100):
    if len(a)<=window_size+1:
        return [np.mean(a)]
    else:
        return [np.mean(a[i:i+window_size]) for i in range(0,len(a)-window_size)]

def visualizeAndSave(train_loss, valid_loss, figName):
    # visualize the loss as the network trained
    fig = plt.figure(figsize=(10,8))
    plt.plot(range(1,len(train_loss)+1),train_loss, label='Training Loss')
    plt.plot(range(1,len(valid_loss)+1),valid_loss,label='Validation Loss')

    # find position of lowest validation loss
    minposs = valid_loss.index(max(valid_loss))+1 
    plt.axvline(minposs, linestyle='--', color='r',label='Early Stopping Checkpoint')

    plt.xlabel('epochs')
    plt.ylabel('loss')
    plt.xlim(0, len(train_loss)+1) # consistent scale
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    fig.savefig(figName, bbox_inches='tight')


# In[3]:


import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import math
from scipy.stats import randint
import DiscreteCondEnt as DC

from sklearn.linear_model import LinearRegression
linReg = LinearRegression()

def varEntropy(y):
    return np.log(np.var(y)*np.pi*2)/2

from sklearn.metrics import mean_squared_error
def MSEscorer(clf, X, y):
    y_est = clf.predict(X)
    return np.log(mean_squared_error(y, y_est)*np.pi*2)/2


# In[5]:


MINE2 = []
Reg2 = []
GT2 = []
COV2 = []
CVFold = 3
MINEsize2 = 100
def worker_Train_Mine_cov(input_arg):
    cov, MINEsize = input_arg
    MINEsize = int(MINEsize)
    x = np.transpose(np.random.multivariate_normal( mean=[0,0],
                                  cov=[[1,cov],[cov,1]],
                                 size = MINEsize * 1000))
    DE = DC.computeEnt(x, linReg, MSEscorer, varEntropy, CVFold)
    MI = DE[1,0] + DE[0,0] - DE[0,1] - DE[1,1]
    MI = MI/2
    REG = MI

    GT = -0.5*np.log(1-cov*cov)

    mine_net = Mine()
    mine_net_optim = optim.Adam(mine_net.parameters(), lr=1e-3)
    mine_net,tl ,vl = train(np.transpose(x),mine_net,mine_net_optim, verbose=False, batch_size=MINEsize, patience=50)
    result_ma = ma(vl)
    MINE = result_ma[-1]
    filename = "MINE_Train_Fig_cov={0}_size={1}.png".format(cov,MINEsize)
    visualizeAndSave(tl, vl, filename)

    return cov, MINE, REG, GT

from multiprocessing.dummy import Pool as ThreadPool

def ParallelWork_cov(Size0):
    numThreads = 9
    cov = 1 - 0.5**np.arange(numThreads)
    size = int(Size0)*np.ones(numThreads)
    inputArg = np.concatenate((cov[:,None],size[:,None]),axis=1).tolist()
    pool = ThreadPool(numThreads)
    results = pool.map(worker_Train_Mine_cov, inputArg)
    pool.close()
    pool.join()
    return results

result = np.array(ParallelWork_cov(MINEsize2))
COV2 = result[:,0]
MINE2 = result[:,1]
Reg2 = result[:,2]
GT2 = result[:,3]

fig,ax = plt.subplots()
ax.scatter(COV2, MINE2, c='b', label='MINE')
ax.scatter(COV2, Reg2, c='r', label='Regressor')
ax.scatter(COV2, GT2, c='g', label='Ground Truth')

ax.legend()
filename = "MINE_Upper_bound_size={0}".format(MINEsize2)
fig.savefig(filename, bbox_inches='tight')

fig2, ax2 = plt.subplots()
COV22 = np.log(np.ones(len(COV2)) - COV2)
ax2.scatter(COV22, MINE2, c='b', label='MINE')
ax2.scatter(COV22, Reg2, c='r', label='Regressor')
ax2.scatter(COV22, GT2, c='g', label='Ground Truth')

ax2.legend()
filename = "MINE_Upper_bound_log_size={0}".format(MINEsize2)
fig2.savefig(filename, bbox_inches='tight')


MINE2 = []
Reg2 = []
GT2 = []
COV2 = []
CVFold = 3
cov = 0.9999
# for i in range(1, 10):
#     size2 = 2**i
#     COV2.append(cov)
#     x = np.transpose(np.random.multivariate_normal( mean=[0,0],
#                                   cov=[[1,cov],[cov,1]],
#                                  size = 100*size2))
#     DE = DC.computeEnt(x, linReg, MSEscorer, varEntropy, CVFold)
#     MI = DE[1,0] + DE[0,0] - DE[0,1] - DE[1,1]
#     MI = MI/2
#     Reg2.append(MI)
#     #plt.scatter(cov, MI, c='g',label='KNN-regressor')
#     groundTruth = -0.5*np.log(1-cov*cov)
#     GT2.append(groundTruth)
#     #plt.scatter(cov, groundTruth, c='r',label='ground truth')
    
#     #MINE
#     mine_net = Mine()
#     mine_net_optim = optim.Adam(mine_net.parameters(), lr=1e-3)
#     mine_net,tl ,vl = train(np.transpose(x),mine_net,mine_net_optim, verbose=False, patience=50, batch_size=size2)
#     result_ma = ma(vl)
#     MINE2.append(result_ma[-1])
#     filename = "MINE_Train_Fig_sampleSize={0}_cov={1}.png".format(size2,cov)
#     visualizeAndSave(tl, vl, filename)
#     #MINE

def ParallelWork_size(Cov0):
    numThreads = 9
    size = int(2)**np.arange(numThreads)
    cov = int(Cov0)*np.ones(numThreads)
    inputArg = np.concatenate((cov[:,None],size[:,None]),axis=1).tolist()
    pool = ThreadPool(numThreads)
    results = pool.map(worker_Train_Mine_cov, inputArg)
    pool.close()
    pool.join()
    return results

result = np.array(ParallelWork_size(cov))
COV2 = result[:,0]
MINE2 = result[:,1]
Reg2 = result[:,2]
GT2 = result[:,3]


fig,ax = plt.subplots()
ax.scatter(COV2, MINE2, c='b', label='MINE')
ax.scatter(COV2, Reg2, c='r', label='Regressor')
ax.scatter(COV2, GT2, c='g', label='Ground Truth')

ax.legend()
filename = "MINE_size_Upper_bound_cov={0}".format(cov)
fig.savefig(filename, bbox_inches='tight')

fig2, ax2 = plt.subplots()
COV22 = np.log(np.ones(len(COV2)) - COV2)
ax2.scatter(COV22, MINE2, c='b', label='MINE')
ax2.scatter(COV22, Reg2, c='r', label='Regressor')
ax2.scatter(COV22, GT2, c='g', label='Ground Truth')

ax2.legend()
filename = "MINE_size_log_Upper_bound_cov={0}".format(cov)
fig2.savefig(filename, bbox_inches='tight')
