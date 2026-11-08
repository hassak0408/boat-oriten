"""試し：毎日の一覧（jpipe.py）を、置き場を STORE/jra/exp/picks に替えて動かす（本物の一覧を上書きしない。GitHub の方の jra-exp で動かす）。
使い方：python jk_pipetest.py STORE 日付YYYYMMDD"""
import os, sys, runpy
os.environ['PICKS_DIR'] = 'jra/exp/picks'
sys.argv = ['jpipe.py', sys.argv[1], sys.argv[2]]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jpipe.py'), run_name='__main__')
