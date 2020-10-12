#!/usr/bin/env python


import pandas as pd
import numpy as np
import pickle
from ashleyslib.train_classification_model import get_relative_features


def add_prediction_parser(subparsers):
    parser = subparsers.add_parser('predict', help='predict class probabilities for new cells')
    parser.add_argument('--path', '-p', help='path to feature table of data that should be predicted', required=True)
    parser.add_argument('--output', '-o', help='folder for output file', required=True)
    parser.add_argument('--model', '-m', help='pkl model to use for prediction', required=True)
    parser.add_argument('--annotation', '-a', help='path to folder with annotation files', required=False)
    parser.add_argument('--filter', dest='filter', action='store_true')
    parser.add_argument('--no-filter', dest='filter', action='store_false')
    parser.add_argument('--relative', dest='relative', action='store_true', default=False, required=False, help='using only relative features')
    parser.set_defaults(filter=False)

    parser.set_defaults(execute=run_prediction)

    return subparsers


def predict_model(model_name, features):
    with open(model_name, 'rb') as m:
        clf = pickle.load(m)
        prediction = clf.predict(features)
        probability = clf.predict_proba(features)[:, 1]
    return prediction, probability


def evaluate_prediction(probability, annotation, dataset, output, critical_bound):
    names = dataset['sample_name'].values
    class_list = []
    with open(annotation) as f:
        annotation_list = [line.rstrip() for line in f]

    for n in names:
        if n in annotation_list:
            class_list.append(1)
        else:
            class_list.append(0)

    tp = 0
    fp = 0
    tn = 0
    fn = 0
    fn_cells = []
    fp_cells = []
    fn_critical = []
    fp_critical = []
    for p, c, n in zip(probability, class_list, names):
        if c == 1:
            if p < 0.5:
                fn += 1
                fn_cells.append(n)
                if p > critical_bound[0]:
                    fn_critical.append(n)
            else:
                tp += 1
        else:
            if p < 0.5:
                tn += 1
            else:
                fp += 1
                fp_cells.append(n)
                if p < critical_bound[1]:
                    fp_critical.append(n)

    with open(output + 'prediction_accuracy.tsv', 'w') as f:
        f.write('false positive predictions: ' + str(fp_cells) + '\n')
        f.write('false positive and critical predictions: ' + str(fp_critical) + '\n')
        f.write('false negative predictions: ' + str(fn_cells) + '\n')
        f.write('false negative and critical predictions: ' + str(fn_critical) + '\n')
        f.write('accuracy: ' + str((tp + tn)/(tp+tn+fp+fn)) + '\n')
        f.write('F1 score: ' + str((2*tp)/(2*tp + fp + fn)) + '\n')
        f.write('tp: ' + str(tp) + ', tn: ' + str(tn) + ', fp: ' + str(fp) + ', fn: ' + str(fn))
    return


def filter_low_read_counts(dataset):
    cut = 23000
    filtered = dataset.loc[dataset['total_0.2mb'] < cut]
    index_names = dataset[dataset['total_0.2mb'] < cut].index
    dataset.drop(index_names, inplace=True)
    filtered_names = filtered['sample_name'].values
    return filtered_names


def run_prediction(args):
    model = args.model
    path = args.path
    output = args.output
    annotation = args.annotation
    filter_cells = args.filter

    critical_bound = (0.3, 0.7)
    dataset = pd.read_csv(path, sep='\s+')
    if args.relative:
        dataset = get_relative_features(dataset)
    features = dataset.drop(columns=['sample_name'])
    names = dataset['sample_name'].values

    prediction, probability = predict_model(model, features)

    if filter_cells:
        filtered_cells = filter_low_read_counts(dataset)
        names = np.concatenate((names, filtered_cells))
        prediction_filtered = [0] * len(filtered_cells)
        prediction = np.concatenate((prediction, prediction_filtered))
        probability = np.concatenate((probability, prediction_filtered))

    if annotation is not None:
        evaluate_prediction(probability, annotation, dataset, output, critical_bound)

    file = open(output + 'prediction_probabilities.tsv', 'w')
    critical = open(output + 'critical_predictions.tsv', 'w')
    file.write('cell\tprediction\tprobability\n')
    critical.write('cell\tprobability\n')
    for i in range(len(names)):
        file.write(names[i] + '\t' + str(prediction[i]) + '\t' + str(round(probability[i], 4)) + '\n')
        if critical_bound[0] < probability[i] < critical_bound[1]:
            critical.write(names[i] + '\t' + str(round(probability[i], 4)) + '\n')

    file.close()
