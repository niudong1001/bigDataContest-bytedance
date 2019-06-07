import csv
import os
import sys
import config
sys.path.append(config.GLOBAL_DIR)
from helper import Timer
from gensim.models import Word2Vec
# from gensim.models.word2vec import LineSentence
import argparse

parser = argparse.ArgumentParser(description='Build word2vec.')
parser.add_argument('-f', '--file', type=str, help='sentences file to process')
parser.add_argument('-d', '--save-dir', type=str, help='dir for save')
parser.add_argument('-m', '--save-model', type=str, help='file name for save model')
# parser.add_argument('-v', '--save-vector', type=str, help='file name for save vector')
args = parser.parse_args()

if not args.file or not os.path.isfile(args.file):
    print("Not a valid file.")
    exit()
if not args.save_dir or not os.path.isdir(args.save_dir):
    print("Not a valid dir.")
    exit()

class SentenceStream(object):
    def __init__(self, dirname):
        self.dirname = dirname

    def __iter__(self):
        for line in open(self.dirname):
            yield line.split()

if __name__ == "__main__":

    # python build_word2vec.py -f "../input/word2vec_sentences.txt" -d "../output/" -m "word2vec.model" -v "word2vec.kv"

    with Timer("Build word2vec"):
        # a memory-friendly iterator
        sentences = SentenceStream(args.file)
        # https://rare-technologies.com/word2vec-tutorial/
        # https://radimrehurek.com/gensim/models/word2vec.html
        # https://blog.csdn.net/szlcw1/article/details/52751314
        # https://github.com/lzhenboy/word2vec-Chinese/blob/master/word2vec_train.py
        # https://www.jianshu.com/p/6a34929c165e
        model = Word2Vec(sentences, size=200, window=5, min_count=5, workers=4, batch_words=500000)
        model.save(os.path.join(args.save_dir, args.save_model))
        # model.wv.save(os.path.join(args.save_dir, args.save_vector))
        # model.wv.save_word2vec_format(os.path.join(args.save_dir, args.save_vector),binary=False)