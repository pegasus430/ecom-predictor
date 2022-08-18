import os
import logging

import psutil  # pip install psutil


def get_memory_usage_for_all_processes(max_processes=7):
    process_dict = {}
    pids = [p.pid for p in psutil.process_iter()]
    for pid in pids:
        try:
            p = psutil.Process(pid)
            process_memory_percents = p.memory_percent()
            if p.name() in process_dict:
                process_dict[p.name()] += process_memory_percents
            else:
                process_dict[p.name()] = process_memory_percents
        except Exception as _:
            continue

    process_list = process_dict.items()
    process_list = sorted(process_list, key=lambda k: k[1], reverse=True)
    return process_list[0:max_processes]


def get_cpu_usage_for_all_processes(max_processes=7):
    process_dict = {}
    pids = [p.pid for p in psutil.process_iter()]
    for pid in pids:
        try:
            p = psutil.Process(pid)
        except Exception as _:
            continue
        try:
            process_cpu_percents = p.cpu_percent(0.01)
            if p.name() in process_dict:
                process_dict[p.name()] += process_cpu_percents
            else:
                process_dict[p.name()] = process_cpu_percents
        except Exception as _:
            continue

    process_list = process_dict.items()
    process_list = sorted(process_list, key=lambda k: k[1], reverse=True)
    return process_list[0:max_processes]


def get_memory_usage_for_current_process():
    try:
        current_process = psutil.Process(os.getpid())
    except Exception as _:
        return 0
    mem = current_process.memory_percent()
    for child in current_process.children(recursive=True):
        mem += child.memory_percent()
    return mem


def get_cpu_usage_for_current_process():
    try:
        current_process = psutil.Process(os.getpid())
    except Exception as _:
        return 0
    cpu = current_process.cpu_percent(0.01)
    for child in current_process.children(recursive=True):
        try:
            cpu += child.cpu_percent(0.01)
        except psutil.NoSuchProcess:
            pass
    return cpu


def get_memory_usage_percent():
    return psutil.virtual_memory().percent


def get_swap_usage_percent():
    return psutil.swap_memory().percent


def get_disk_usage_percent():
    return psutil.disk_usage('/').percent


def get_cpu_usage_percent():
    return psutil.cpu_percent()


def report_statistics(report_cpu_map=False):
    try:
        return {
            'disk_usage_total': get_disk_usage_percent(),
            'swap_usage_total': get_swap_usage_percent(),
            'cpu_usage_total': get_cpu_usage_percent(),
            'cpu_usage_by_process': get_cpu_usage_for_all_processes() if report_cpu_map else 'not reported',
            'cpu_usage_for_current_process': get_cpu_usage_for_current_process(),
            'ram_usage_total': get_memory_usage_percent(),
            'ram_usage_by_process': get_memory_usage_for_all_processes(),
            'ram_usage_for_current_process': get_memory_usage_for_current_process(),
        }
    except:
        logger = logging.getLogger('main_log')
        logger.exception('Statistics')
        return {}


if __name__ == '__main__':
    print report_statistics()
