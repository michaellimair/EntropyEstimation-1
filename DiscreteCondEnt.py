import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math
from scipy.stats import randint

def MutualInfo(rv):
    histRV = np.array(np.unique(rv[0], axis=0, return_counts=True)[1])[None,:]
    histRV2 = np.array(np.unique(rv[(0,1),:], axis=1, return_counts=True)[1])[None,:]
    for i in range(1, numRV):
        histRV = np.append(histRV, np.array(np.unique(rv[i], axis=0, return_counts=True)[1])[None,:], axis=0)
        if i!=1:
            for j in range(i):
                newArr = np.unique(rv[(j,i),:], axis=1, return_counts=True)
                histRV2 = np.append(histRV2, np.array(newArr[1])[None,:], axis=0)
    pmfRV = histRV/RVsize
    pmfRV2 = histRV2/RVsize
    H = -1*np.average(np.log(pmfRV), weights=pmfRV, axis=1)
    H2 = -1*np.average(np.log(pmfRV2), weights=pmfRV2, axis=1)
    MI = np.zeros(H2.shape)
    index = 0
    for i in range(1, numRV):
        for j in range(i):
            MI[index] = H2[index] - H[i] - H[j]
            index = index + 1
    return MI

from scipy.special import comb
def subset(size, index):
    subset = [-1]
    sum = 0
    for numOutput in range(size + 1):
        c = comb(size, numOutput)
        if index >= sum + c:
            sum += c
        else:
            break
    #print (numOutput)
    numLeft = numOutput
    for candidate in range(size-1, -1, -1):
        if index == sum:
            for remaining in range(numLeft-1, -1, -1):
                if subset[0] == -1:
                    subset[0] = remaining
                else:
                    subset = np.append(subset, remaining)
            break
        elif 0 == numLeft:
            break
        elif (index - sum) >= comb(candidate, numLeft):
            sum += comb(candidate, numLeft)
            if subset[0] == -1:
                subset[0] = candidate
            else:
                subset = np.append(subset, candidate)
            numLeft -= 1
    #print(output)
    if subset[0] != -1:
        return subset

def ConditionSet(size, Resp, index):
    set = subset(size - 1, index)
    cond = [-1]
    for element in set:
        if element >= Resp:
            element += 1
        if cond[0] == -1:
            cond[0] = element
        else:
            cond = np.append(cond, element)
    return cond

def DiscreteEntropy(y):
    #cols = y.shape[y.ndim-1]
    #rows = y.shape[0]
    pmf = np.unique(y, return_counts=True, axis=y.ndim-1)[1]/y.shape[y.ndim-1]
    return -1*np.average(np.log(pmf), weights=pmf)

from scipy.special import softmax
def NegLogLikeScorer_Softmax(estimator, X, y):
    y_est = estimator.predict_proba(X)
    sm_est = softmax(y_est, axis=1)
    y_like, count = np.unique(sm_est[np.arange(y.size), y], return_counts=True)
    if 0 == y.size:
        return -1
    #ignore 0 likelihood
    if 0 == y_like[0]:
        nom = -1*np.average(np.log(y_like[1:]), weights=count[1:])
        if 1 == y.size:
            return 0
    else:
        nom = -1*np.average(np.log(y_like), weights=count)
    return nom/y.size

def NegLogLikeScorer(estimator, X, y):
    y_est = estimator.predict_proba(X)
    y_like, count = np.unique(y_est[np.arange(y.size), y], return_counts=True)
    if 0 == y.size:
        return -1
    #ignore 0 likelihood
    if 0 == y_like[0]:
        nom = -1*np.average(np.log(y_like[1:]), weights=count[1:])
        if 1 == y.size:
            return 0
    else:
        nom = -1*np.average(np.log(y_like), weights=count)
    return nom/y.size

def CondDEntropyScorer(estimator, X, y):
    y_est = estimator.predict(X)
    #print (np.unique(np.array([y,y_est]), return_counts=True, axis=1))
    return DiscreteEntropy(np.array([y,y_est])) - DiscreteEntropy(y_est)



# from sklearn.metrics import mean_squared_error
# def ContinuousEntropy(y):
#     if 1 == y.ndim:
#         return np.log(np.var(y))
#     else:
#         return np.log(mean_squared_error(y[0], y[1]))

# def CondCEntropyScorer(estimator, X, y):
#     y_est = estimator.predict(X)
#     #print (np.unique(np.array([y,y_est]), return_counts=True, axis=1))
#     return ContinuousEntropy(np.array([y,y_est])) - ContinuousEntropy(y_est)

'''
CART
'''
#from sklearn import tree
#clf = tree.DecisionTreeClassifier() #Good for high==2


'''
SVM
'''
#from sklearn import svm
#clf = svm.SVC(gamma='scale', decision_function_shape='ovo') #Not sure

'''
KNN
'''
# from sklearn import neighbors
# #clf = neighbors.NearestCentroid() #Not sure
# numNeighbors = high
# clf = neighbors.KNeighborsClassifier(numNeighbors) #better than CART


from sklearn.model_selection import cross_val_score
#print (cross_val_score(clf,np.transpose(rv[ConditionSet(numRV, 0, 6)]), rv[0], cv=3, scoring=CondEntropyScorer))


def computeEnt(rv, clf, scorer, CV_Fold):
    num_RV = rv.shape[0]
    _high = np.amax(rv)
    _low = np.amin(rv)
    numComb = np.power(2, num_RV - 1)
    DEntropy = np.zeros((num_RV, numComb))
    print (num_RV, " Discrete RVs with range [", _low, ", ", _high, "]")
    print ("Resp\tCond\tH(Resp|Cond)")
    for Resp in range(num_RV):
        DEntropy[Resp,0] = DiscreteEntropy(rv[Resp])
        for sI in range(1, numComb):
            DEntropy[Resp,sI] = np.mean(cross_val_score(clf,np.transpose(rv[ConditionSet(num_RV, Resp, sI)]), rv[Resp], cv=CV_Fold, scoring=scorer))
            print (Resp, "\t", ConditionSet(num_RV, Resp, sI), "\t", DEntropy[Resp,sI])
    return DEntropy

def getRandomVar_select(method, low, high, RVsize, numRV, depend):
    rv = np.split(method(low, high, size=RVsize*(numRV - 1)), numRV - 1)
    rv_sel = np.array(rv)[depend]
    rv = np.append(rv, np.remainder(np.sum(rv_sel, axis=0), high)[None,:], axis=0)
    return rv

def getRandomVar(method, low, high, RVsize, numRV):
    rv = np.split(method(low, high, size=RVsize*(numRV - 1)), numRV - 1)
    rv = np.append(rv, np.remainder(np.sum(rv, axis=0), high)[None,:], axis=0)
    return rv

if __name__ == "__main__":
    #ground truth
    low, high, RVsize, numRV = 0, 3, 1000, 6
    depend = np.array([0, 1, 3])
    rv = getRandomVar_select(randint.rvs, low, high, RVsize, numRV, depend)

    from sklearn import neighbors
    numNeighbors = high
    clf = neighbors.KNeighborsClassifier(numNeighbors)

    CVFold = 3
    computeEnt(rv, clf, NegLogLikeScorer_Softmax, CVFold)