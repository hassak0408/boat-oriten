"""試し：地方の毎朝の一覧（pipe.py）を、置き場を STORE/data/exp/picks に替えて動かす（本物の一覧を上書きしない。GitHub の方の chiho-exp で動かす）。
使い方：python nk_pipetest.py STORE 日付YYYYMMDD"""
import os, sys, runpy
os.environ['PICKS_DIR'] = 'data/exp/picks'
sys.argv = ['pipe.py', sys.argv[1], sys.argv[2]]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipe.py'), run_name='__main__')
