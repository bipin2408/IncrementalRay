# COL733 Project

## Ray Setup and run basic test

### Ray can also be installed as a conda package on Linux

`conda create -c conda-forge python=3.9 -n ray`
`conda activate ray`

### Ray with support for the dashboard + cluster launcher
`conda install -c conda-forge "ray-default"`

### Can also do in a new conda env:
`pip install ray`

### Test if the installation succeeded:
 In ray/python/ray: pytest -v tests/test_mini.py 

 > might want to change the file python/ray/types.py to _types.py, if facing circular import issues, there might be a better way to do this.

- Added the test_lcs.py file in the tests folder, to test the lcs implementation. `python test_lcs.py`



## Ray Design Patterns: 
https://docs.google.com/document/d/167rnnDFIVRhHhK4mznEIemOtj63IOhtIPvSYaPgI4Fg/edit?tab=t.0#heading=h.crt5flperkq3

## Ray v2 Architecture: 
https://docs.google.com/document/d/1tBw9A4j62ruI5omIJbMxly-la5w4q_TjyJgJL_jN2fI/preview?tab=t.0

## Introduction:

## Learning Goals:

## Assumptions:

## Approach:
