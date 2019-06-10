'''
@Author: niudong
@LastEditors: niudong
@Date: 2019-06-07 22:12:50
@LastEditTime: 2019-06-10 21:18:38
'''
import os
import json
import sys
import time
import pickle
import numpy as np
import pandas as pd
from .config import GLOBAL_DIR, K_FOLD, OUTPUT_DIR, OUTPUT_TRAIN_DIR, OUTPUT_TEST_DIR
sys.path.append(GLOBAL_DIR)
# https://www.jianshu.com/p/35eed1567463
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
# from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from .models import LigthGBM_GBDT, LigthGBM_DART
from helper import Timer, MyEncoder, usetime, OFFLINE
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score


model_map = {
    'lgb_dart': LigthGBM_DART,
    'lgb_gbdt': LigthGBM_GBDT,
    # 'sklearn_rf': Sklearn_RF,
    # 'torch_nn': Torch_DNN
}
X, y = None, None
test_X, test_y = None, None


def LoadDataset(in_train_feature, in_train_label, in_test_feature, in_test_label=None):

    global X, y, test_X, test_y

    @usetime("load train dataset")
    def _load_train():
        X = np.load(in_train_feature)
        y = np.load(in_train_label)
        return X, y

    @usetime("load test dataset")
    def _load_test():
        X = np.load(in_test_feature)
        if OFFLINE:
            y = np.load(in_test_label)
            return X, y
        else:
            return X
    
    X, y =  _load_train()
    if OFFLINE:
        test_X, test_y = _load_test()
    else:
        test_X = _load_test()

    print("X:", X.shape, X[:2])
    print("y:", y.shape, y[:2])
    print("Test x:", test_X.shape, test_X[:2])
    if OFFLINE:
        print("Test y:", test_y.shape, test_y[:2])


def fn(params):

    model_name = params.pop('model')
    model = model_map[model_name](**params)
    
    print(json.dumps(params, indent=1))

    # Train 
    losses, aucs = [], []
    train_predicts = np.empty_like(y).astype(float)
    stratified_folder = StratifiedKFold(
        n_splits=K_FOLD, 
        random_state=0, 
        shuffle=False
    )
    for train_index, valid_index in stratified_folder.split(X, y):
        train_X, train_y = X[train_index], y[train_index]
        valid_X, valid_y = X[valid_index], y[valid_index]
        loss, auc = model.fit(train_X, train_y, valid_X, valid_y)
        losses.extend(loss)
        aucs.extend(auc)
        train_predicts[valid_index] = model.predict(valid_X)
    timestamp = int(time.time())
    mean, std = np.mean(losses), np.std(losses)
    chunk_auc, total_auc = np.mean(aucs), roc_auc_score(y, train_predicts)
    filename = '%s_%d_%f_%f_%f.npy' % (model_name, timestamp, min(chunk_auc, total_auc), mean, std)
    np.save(os.path.join(OUTPUT_TRAIN_DIR, filename), train_predicts)
    print("Valid AUC (chunk, total):" + str(chunk_auc) + " " + str(total_auc))

    # Test
    model.fit(X, y)
    test_predicts, test_auc = model.predict(test_X), None
    np.save(os.path.join(OUTPUT_TEST_DIR, filename), test_predicts)
    if OFFLINE:
        test_auc = roc_auc_score(test_y, test_predicts)
        print("Test AUC:" + str(test_auc))

    return {
        'loss': mean,
        "chunk_auc": chunk_auc,  # 每个valid块算一次auc,再平均
        "total_auc": total_auc,  # 整体valid算auc
        "test_auc": test_auc,
        'loss_variance': std,
        'status': STATUS_OK,
        'file_name': filename
    }


def run_lgb_gbdt(eval_num=5):
    trials = Trials()
    search_space = {
        'model': 'lgb_gbdt',
        'num_threads':4,
        'num_leaves': hp.quniform('num_leaves', 20, 100, 5),
        'min_data_in_leaf': hp.quniform('min_data_in_leaf', 10, 100, 10),
        'feature_fraction': hp.quniform('feature_fraction', 0.6, 1.0, 0.1),
        'bagging_fraction': hp.quniform('bagging_fraction', 0.6, 1.0, 0.1),
        'bagging_freq': hp.quniform('bagging_freq', 0, 20, 2),
        'max_bin': hp.choice('max_bin', [15, 63, 255, 1023]),
        'learning_rate': hp.quniform('learning_rate', 0.01, 0.1, 0.01),
        'num_iterations': hp.quniform('num_iterations', 20, 220, 40)
    }
    best_param = fmin(fn, space=search_space,
                        algo=tpe.suggest,
                        max_evals=eval_num,
                        trials=trials)


    info = trials.best_trial
    info['param'] = best_param

    json.dump(info, open(OUTPUT_DIR+'lgb_gbdt_best_info.json','w'),indent=1, cls=MyEncoder)


def run_lgb_dart(eval_num=5):
    trials = Trials()
    search_space = {
        'model': 'lgb_dart',
        'num_threads':4,
        'drop_rate': hp.quniform('drop_rate', 0.5, 1, 0.1),
        'skip_drop': hp.quniform('skip_drop', 0.5, 1, 0.1),
        'num_leaves': hp.quniform('num_leaves', 20, 100, 5),
        'min_data_in_leaf': hp.quniform('min_data_in_leaf', 10, 100, 10),
        'feature_fraction': hp.quniform('feature_fraction', 0.6, 1.0, 0.1),
        'bagging_fraction': hp.quniform('bagging_fraction', 0.6, 1.0, 0.1),
        'bagging_freq': hp.quniform('bagging_freq', 0, 20, 2),
        'max_bin': hp.choice('max_bin', [15, 63, 255, 1023]),
        'learning_rate': hp.quniform('learning_rate', 0.01, 0.1, 0.01),
        'num_iterations': hp.quniform('num_iterations', 20, 220, 40)
    }
    best_param = fmin(fn, space=search_space,
                        algo=tpe.suggest,
                        max_evals=eval_num,
                        trials=trials)


    info = trials.best_trial
    info['param'] = best_param

    json.dump(info, open(OUTPUT_DIR+'lgb_dart_best_info.json','w'),indent=1, cls=MyEncoder)