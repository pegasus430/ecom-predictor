# **DO NOT DO THIS IF YOU ARE NOT A LEAD DEV** #

To deploy a CH ticket into production:

First, you need to know the commit id(s) corresponding to the merges of the branch into master. There may be more than one. If the branch is named Bug123Issue, go to your local tmtext repo and run:


```
#!shell

git checkout master
git pull 
git log | grep -B 5 Bug123Issue
```


This will show you one or more commit ids like:


```
#!shell

commit e827980b50613133d7ef0faf83cf6bd1a2239fc1

```

Then do:


```
#!shell

git checkout production
git pull
git cherry-pick -m 1 <commit id 1>
git cherry-pick -m 1 <commit id 2>
git push
```


If anything goes wrong:


```
#!shell

git cherry-pick --abort
```


But nothing will be deployed to production if you don't run 'git push'