Simple workflow for working on a separate branch
-------------------------------------------------------------------

Scenario: assume the main branch is `master`, and you want to create `tesco-scraper` to push to and be merged into master.

#### You will do this once:

    $ git checkout master # be sure you are on master
    $ git checkout -b tesco-scraper # create your branch

#### You will do this everytime you write code:

    $ git checkout tesco-scraper # be sure you are on your branch

Then write your code, commit. Then push to your branch:

    $ git push origin tesco-scraper

#### You will do this periodically, before pushing, to be up to date with the changes on master:

    $ git checkout master # switch to master
    $ git pull origin master # pull remote changes from master to local master
    $ git checkout tesco-scraper # switch back to your branch
    $ git merge master # merge master changes into your branch

The last step (merge) might cause conflicts. If they happen, you can try to solve them using a mergetool, or if you're not sure let the developer responsible for master know so you can decide on what version of the code to keep together.

*Note*: the `git checkout tesco-scraper` step was added every time to make sure you are on the right branch; if you are you can omit it.

When using the same branch as other developers
-----------------------------------------------------------------------

To pull remote changes on one specific branch (e.g. you're on master and want to get the latest changes from upstream)

    $ git checkout master # be sure you're on master
    $ git pull origin master
