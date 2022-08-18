from sklearn import svm
import csv
import numpy as np
import os
import matplotlib.pyplot as plt
import sys, os
from math import sin, cos, sqrt, pi
import cv2.cv as cv
import urllib2
from numpy import array as nparray, median as npmedian
from sklearn.externals import joblib
from extract_text import extract_text

# toggle between CV_HOUGH_STANDARD and CV_HOUGH_PROBILISTIC
USE_STANDARD = False


CWD = os.path.dirname(os.path.abspath(__file__))


def extract_features(filename, is_url=False):
    '''Extracts features to be used in text image classifier.
    :param filename: input image
    :param is_url: is input image a url or a file path on disk
    :return: tuple of features:
    (average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_straight_lines)
    Most relevant ones are average_slope, average_differences and nr_straight_lines.
    '''

    if is_url:
        filedata = urllib2.urlopen(filename).read()
        imagefiledata = cv.CreateMatHeader(1, len(filedata), cv.CV_8UC1)
        cv.SetData(imagefiledata, filedata, len(filedata))
        src = cv.DecodeImageM(imagefiledata, cv.CV_LOAD_IMAGE_GRAYSCALE)
    else:
        src = cv.LoadImage(filename, cv.CV_LOAD_IMAGE_GRAYSCALE)

    # normalize size
    normalized_size = 400

    # smaller dimension will be 400, longer dimension will be proportional
    orig_size = cv.GetSize(src)

    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)
    dst = cv.CreateImage(new_size, 8, 1)
    cv.Resize(src, dst)
    # cv.SaveImage("/tmp/resized.jpg",dst)
    src = dst

    dst = cv.CreateImage(cv.GetSize(src), 8, 1)
    color_dst = cv.CreateImage(cv.GetSize(src), 8, 3)
    storage = cv.CreateMemStorage(0)

    cv.Canny(src, dst, 50, 200, 3)
    cv.CvtColor(dst, color_dst, cv.CV_GRAY2BGR)

    slopes = []
    # difference between xs or ys - variant of slope
    tilts = []
    # x coordinates of horizontal lines
    horizontals = []
    # y coordinates of vertical lines
    verticals = []

    if USE_STANDARD:
        coords = cv.HoughLines2(dst, storage, cv.CV_HOUGH_STANDARD, 1, pi / 180, 50, 50, 10)
        lines = []
        for coord in coords:
            (rho, theta) = coord
            a = cos(theta)
            b = sin(theta)
            x0 = a * rho
            y0 = b * rho
            pt1 = (cv.Round(x0 + 1000*(-b)), cv.Round(y0 + 1000*(a)))
            pt2 = (cv.Round(x0 - 1000*(-b)), cv.Round(y0 - 1000*(a)))
            lines += [(pt1, pt2)]

    else:
        lines = cv.HoughLines2(dst, storage, cv.CV_HOUGH_PROBABILISTIC, 1, pi / 180, 50, 50, 10)

    # eliminate duplicates - there are many especially with the standard version
    # first round the coordinates to integers divisible with 5 (to eliminate different but really close ones)
    # TODO
    # lines = list(set(map(lambda l: tuple([int(p) - int(p)%5 for p in l]), lines)))

    nr_straight_lines = 0
    for line in lines:
        (pt1, pt2) = line

        # compute slope, rotate the line so that the slope is smallest
        # (slope is either delta x/ delta y or the reverse)
        # add smoothing term in denominator in case of 0
        slope = min(abs(pt1[1] - pt2[1]), (abs(pt1[0] - pt2[0]))) / (max(abs(pt1[1] - pt2[1]), (abs(pt1[0] - pt2[0]))) + 0.01)
        # if slope < 0.1:
        # if slope < 5:
        if slope < 0.05:
            if abs(pt1[0] - pt2[0]) < abs(pt1[1] - pt2[1]):
                # means it's a horizontal line
                horizontals.append(pt1[0])
            else:
                verticals.append(pt1[1])
        if slope < 0.05:
        # if slope < 5:
        # if slope < 0.1:
            nr_straight_lines += 1
        slopes.append(slope)
        tilts.append(min(abs(pt1[1] - pt2[1]), (abs(pt1[0] - pt2[0]))))
        # print slope
    average_slope = sum(slopes)/float(len(slopes))
    median_slope = npmedian(nparray(slopes))
    average_tilt = sum(tilts)/float(len(tilts))
    median_tilt = npmedian(nparray(tilts))
    differences = []
    horizontals = sorted(horizontals)
    verticals = sorted(verticals)
    print "x_differences:"
    for (i, x) in enumerate(horizontals):
        if i > 0:
            # print abs(horizontals[i] - horizontals[i-1])
            differences.append(abs(horizontals[i] - horizontals[i-1]))
    print "y_differences:"
    for (i, y) in enumerate(verticals):
        if i > 0:
            # print abs(verticals[i] - verticals[i-1])
            differences.append(abs(verticals[i] - verticals[i-1]))

    print filename
    print "average_slope:", average_slope
    print "median_slope:", median_slope
    print "average_tilt:", average_tilt
    print "median_tilt:", median_tilt
    median_differences = npmedian(nparray(differences))
    print "median_differences:", median_differences
    if not differences:
        # big random number for average difference
        average_differences = 50
    else:
        average_differences = sum(differences)/float(len(differences))
    print "average_differences:", average_differences
    print "nr_lines:", nr_straight_lines

    # print "sorted xs:", sorted(lines)

    return (average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_straight_lines)


def plot_examples(examples=None):
    '''Plots in 2D space the points in the 4 lists given as input
    :param examples: list of nutrition images,
    dictionaries with keys:
    'name' - image title
    'label' - one of 'TP', 'TN', 'FP', 'FN' (true/false positives/negatives)
    'coords' - tuple of coordinates
    '''

    # hardcode list of examples
    if not examples:
        examples = get_examples_from_files()
        examples += get_examples_from_images()

    labels_to_colors = {
    'TP' : 'red',
    'FN' : 'orange',
    'TN' : 'blue',
    'FP' : 'green',
    }

    points = []

    import matplotlib.pyplot as plt

    X = []
    Y = []
    colors = []
    areas = []

    print examples
    for example in examples:
        x, y = example['coords'][:2]

        X.append(x)
        Y.append(y)
        color = labels_to_colors[example['label']]
        colors.append(color)
        areas.append(example['coords'][2])

    plt.scatter(X, Y, s=areas, c=colors)
    plt.savefig('/tmp/nutrition.png')
    plt.show()


def get_examples_from_images():
    images = [
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition2.jpg', 'TN'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition3_falsepos.jpg', 'FP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition4_falsepos.jpg', 'FP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition5_falsepos.jpg', 'FP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition6_falsepos.jpg', 'FP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/notnutrition.jpg', 'TN'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image10_falseneg.jpg', 'FN'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image11_falseneg.jpg', 'FN'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image2.png', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image3.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image4.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image5.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image6.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image7.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image8.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image9.jpg', 'TP'),
                    ('/home/ana/code/tmtext/nutrition_info_images/examples/nutrition_image.jpg', 'TP')
                ]

    examples = []
    for image, label in images:
        average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_lines = extract_features(image)
        example = {'name': image, 'label': label, 'coords': (average_slope, average_differences, nr_lines)}
        examples.append(example)
    return examples


def get_examples_from_screenshots():
    nutrition_facts_screenshots_path = "/home/ana/code/tmtext/nutrition_info_images/nutrition_facts_screenshots"
    images = [os.path.join(nutrition_facts_screenshots_path,fn) for fn in next(os.walk(nutrition_facts_screenshots_path))[2]]
    examples = []
    for image in images:
        average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_lines = extract_features(image)
        example = {'name': image, 'label': 2, 'coords': (average_slope, average_differences, nr_lines)}
        examples.append(example)
    return examples


def get_examples_from_files():
    files = ['/home/ana/code/tmtext/nutrition_info_images/nutrition_images_training.csv',
                '/home/ana/code/tmtext/nutrition_info_images/drug_images_training.csv',
                '/home/ana/code/tmtext/nutrition_info_images/nutrition_images_test.csv']
    examples = []
    for examples_file in files:
        with open(examples_file) as f:
            # skip headers line
            f.readline()
            ireader = csv.reader(f)
            for row in ireader:
                label_raw = row[1]
                image = row[0]
                label = 'TP' if label_raw == '1' else 'TN'
                average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_lines = extract_features(image, is_url=True)
                example = {'name': image, 'label': label, 'coords': (average_slope, average_differences, nr_lines)}
                examples.append(example)
    return examples


def extract_features_main():
    # if len(sys.argv) > 1:
    #     filename = sys.argv[1]
    #     src = cv.LoadImage(filename, cv.CV_LOAD_IMAGE_GRAYSCALE)
    # else:
    #     import sys
    #     sys.exit(0)
    
    # extract_features(filename)

    plot_examples()


def read_images_set_fromdir():
    imagesd = get_examples_from_images()
    tset = ([imaged['name'] for imaged in imagesd],
            ['1' if imaged['label'][1]=='P' else '0' for imaged in imagesd],
            [imaged['coords'] for imaged in imagesd])
    return ([imaged['name'] for imaged in imagesd],
            [imaged['coords'] for imaged in imagesd],
            [1 if imaged['label'][1]=='P' else 0 for imaged in imagesd])


def read_images_set_from_screenshots():
    imagesd = get_examples_from_screenshots()
    return ([imaged['name'] for imaged in imagesd],
            [imaged['coords'] for imaged in imagesd],
            [imaged['label'] for imaged in imagesd])


def read_images_set(path="nutrition_images_training.csv"):
    '''Reads the training set from a file, returns examples and their labels (2 lists)
    examples will have the following format:
    tuple of:
    - list of strings representing the image names
    - list of tuples representing the features:
    (average slope, average distance between lines parallel to axes, nr of lines parallel to axes)
    - list of labels: labels will be 1 (text) or 0 (not text)
    '''

    examples = []
    labels = []
    names = []
    with open(path) as f:
        reader = csv.reader(f, delimiter=',', quotechar='"')
        # omit headers
        f.readline()
        for row in reader:
            image = row[0]
            names.append(image)

            average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_straight_lines = \
            extract_features(image, is_url=True)
            examples.append((average_slope, average_differences, nr_straight_lines))
            labels.append(int(row[1]))
    return (names, examples, labels)


def train(training_set, serialize_file=None):
    '''Trains text image classifier.
    :param training_set: training set of images, tuple of lists:
    images, features and labels, as returned by read_images_set.
    :param serialize_file: the path of the file to serialize the classifier to, optional
    :return: tuple of images list and classifier object
    '''
    imgs, X, y = training_set
    clf = svm.SVC(kernel='linear')
    clf.fit(X, y)

    if serialize_file:
        joblib.dump(clf, serialize_file)

    return imgs, clf    


def predict(test_set, clf=None, from_serialized_file=None):
    '''Predicts labels (text image/not) for an input test set.
    :param test_set: test set of images, tuple of lists:
    images, features and labels, as returned by read_images_set.
    :param clf: the classifier object, if passed directly
    :param from_serialized_file: the path of the file containing the serialized classfier, if any
    :return: list of tuples (image_url, label)
    '''
    if from_serialized_file:
        clf = joblib.load(from_serialized_file)

    imgs, examples, labels = test_set
    predicted_examples = []
    for idx, example in enumerate(examples):
        predicted = clf.predict(example)
        # print imgs[idx], labels[idx], predicted
        predicted_examples.append((imgs[idx], predicted[0]))
    return predicted_examples


def load_classifier(path=CWD + "/serialized_classifier/nutrition_image_classifier.pkl"):
    return joblib.load(path)


def predict_one(image, clf=None, from_serialized_file=CWD + "/serialized_classifier/nutrition_image_classifier.pkl", is_url=False):
    '''Predicts label (text image/not) for an input image.
    :param image: image url or path
    :param clf: the classifier object, if passed directly
    :param from_serialized_file: the path of the file containing the serialized classfier, if any
    :param is_url: image is a url, not a file path on disk
    :return: predicted label
    '''
    if not clf and from_serialized_file:
        clf = joblib.load(from_serialized_file)
    average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_straight_lines = \
    extract_features(image, is_url=is_url)
    example = (average_slope, average_differences, nr_straight_lines)

    predicted = clf.predict(example)
    return predicted


def classifier_main():
    training_set1 = read_images_set()
    # trained, clf = train(training_set1, serialize_file="serialized_classifier/nutrition_image_classifier.pkl")

    screenshots_set = read_images_set_from_screenshots()
    goodq_set = read_images_set("nutrition_images_goodq.csv")
    drug_and_supplement_set = read_images_set("drug_images_training.csv")
    training_set2 = [l[:100] for l in screenshots_set]
    training_set3 = [l[:20] for l in goodq_set]
    training_set4 = drug_and_supplement_set

    training_set = [l[0]+l[1] for l in zip(training_set1,training_set4)]

    trained, clf = train(training_set, serialize_file=CWD + "/serialized_classifier/nutrition_image_classifier.pkl")

    test_set1 = read_images_set("nutrition_images_test.csv")
    test_set2 = [l[100:] for l in screenshots_set]
    test_set3 = [l[20:] for l in goodq_set]
    test_set4 = read_images_set("drug_images_test.csv")
    test_set = [l[0]+l[1] for l in zip(test_set1,test_set4)]

    imgs, examples, labels = test_set
    nr_predicted = 0
    predicted = predict(test_set, clf, from_serialized_file=CWD + "/serialized_classifier/nutrition_image_classifier.pkl")
    # predicted = predict(test_set, clf)
    accurate = 0
    with open('nutrition_images_predicted.csv', 'w+') as out:
        for example in predicted:
            out.write(",".join([example[0], str(example[1])]) + "\n")
            if example[1]!=labels[nr_predicted]:
                print "Inaccurate:", example[0]
            else:
                accurate+=1

            nr_predicted += 1

    accuracy = float(accurate)/len(predicted)*100

    print "Accuracy: {0:.2f}%".format(accuracy)

    # Plot the decision boundary
    w = clf.coef_[0]
    print "coefs", clf.coef_
    a = -w[0] / w[1]
    xx = np.linspace(-5, 5)
    yy = a * xx - (clf.intercept_[0]) / w[1]

    plt.plot(xx, yy, 'k-')
    # plt.ylim([0,5])

    plt.scatter([e[0] for e in examples], [e[1] for e in examples], c=['red' if l==1 else 'blue' for l in labels])

    plt.show()


def classifier_predict_one(image_url, clf=None):
    if image_url.startswith("http"):
        is_url = True
    else:
        is_url = False
    predicted = predict_one(image_url, clf, from_serialized_file=CWD + "/serialized_classifier/nutrition_image_classifier.pkl", is_url=is_url)
    return predicted[0]


def predict_textimage_type(image_url):
    '''Decides if text image is nutrition facts image,
    drug facts image or supplement facts image,
    by trying to extract the text in the image
    Returns one of 4 values (strings):
    nutrition_facts, drug_facts, supplement_facts, 
    or None if type could not be determined
    '''

    text = extract_text(image_url, is_url=True)

    if 'nutrition' in text.lower().split():
        return "nutrition_facts"

    if 'drug' in text.lower().split():
        return "drug_facts"

    if 'supplement' in text.lower().split():
        return "supplement_facts"

    return None


def cross_validate(test_set, folds=10):
    '''Validates the classifier by using 10-fold cross-validation.
    Splits the data in 10 parts, iteratively trains on 9 of them and
    tests on the 10th.
    Final accuracy is the average of accuracies for each of the 10 tests.
    :param test_set: input data to validate on, tuple of lists:
    images, features and labels, as returned by read_images_set.
    :returns: accuracy (float)
    '''

    test_sets = []
    imgs, examples, labels = test_set
    # split data into 10 parts
    lg = len(imgs)
    for i in range(folds):
        test_sets.append((imgs[ i*lg/folds : (i+1)*lg/folds ],
            examples[ i*lg/folds : (i+1)*lg/folds ],
            labels[ i*lg/folds : (i+1)*lg/folds ]))

    nr_accurate = 0
    nr_total = 0

    for rnd in range(folds):
        training_set = [[],[],[]]
        for i in range(folds):
            if i != rnd:
                training_set[0] = training_set[0] + test_sets[i][0]
                training_set[1] = training_set[1] + test_sets[i][1]
                training_set[2] = training_set[2] + test_sets[i][2]

        # if there's only one kind of label, skip this set
        if 0 not in training_set[2] or 1 not in training_set[2]:
            print "Skipped validation fold because not enough labels"
            continue

        # train new classifier with this training set
        imgs, clf = train(training_set)

        # test
        imgs, examples, labels = test_sets[rnd]
        for idx, example in enumerate(examples):
                predicted = clf.predict(example)
                # print imgs[idx], labels[idx], predicted
                if labels[idx] == predicted:
                    nr_accurate += 1
                else:
                    print "Inaccurate:", imgs[idx]
                nr_total += 1
        print "nr_accurate", nr_accurate, "/", nr_total


    accuracy = float(nr_accurate)/nr_total

    print "Accuracy: {0:.2f}%".format(accuracy*100)
    return accuracy


if __name__ == '__main__':
    # extract_features_main()
    if len(sys.argv) <= 1:
        classifier_main()
        # 
        # # cross-validate
        # in_set1 = read_images_set("nutrition_images_training.csv")
        # in_set2 = read_images_set("nutrition_images_test.csv")
        # in_set3 = read_images_set("nutrition_images_goodq.csv")
        # in_set4 = read_images_set("drug_images_training.csv")
        # in_set = [l[0]+l[1]+l[2]+l[3] for l in zip(in_set1,in_set2,in_set3,in_set4)]
        # print cross_validate(in_set, 418)
    else:
        print classifier_predict_one(sys.argv[1])
