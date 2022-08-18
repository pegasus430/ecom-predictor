import os
import shutil

if __name__ == '__main__':
    file_list = [
        '/tmp/remote_instance_starter2.log',
        '/tmp/tmp_file',
        '/tmp/log_mod_time_flag',
        '/tmp/post_starter_spiders.log',
        '/tmp/remote_instance_starter.log',
        '/tmp/upload_logs_to_s3.log',
        '/tmp/stop_instances.log',
        '/tmp/check_file_post_starter_root',
        '/tmp/check_file_post_starter_spiders',
        '/tmp/instances_killer_logs.log',
    ]
    # delete all in temporary folder
    for f in file_list:
        try:
            os.remove(f)
        except Exception as e:
            print(str(e))
    # delete job_output folder with all contents
    try:
        shutil.rmtree('/home/spiders/job_output/')
    except Exception as e:
        print(str(e))
    # remove all created zip archives
    try:
        os.system('rm /home/spiders/repo/*.zip')
    except Exception as e:
        print(str(e))
    # remove randon hash_datestamp_data
    try:
        os.remove('/home/spiders/repo/hash_datestamp_data')
    except Exception as e:
        print(str(e))
    # remove all .pyc
    try:
        os.system('rm /home/spiders/repo/*.pyc')
    except Exception as e:
        print(str(e))
    # remove downloaded repo
    try:
        shutil.rmtree('/home/spiders/repo/tmtext')
    except Exception as e:
        print(str(e))
    # remove all markers
    markers = [
        'post_starter_spiders.py.marker',
        'post_starter_root.py.marker',
        'remote_instance_starter.py.marker',
    ]
    for marker in markers:
        try:
            os.remove('/home/spiders/repo/' + marker)
        except Exception as e:
            print(str(e))
    print("All garbage was removed from instance")