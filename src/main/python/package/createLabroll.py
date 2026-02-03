import os
import datetime

from shutil import copyfile
from operator import getitem

from hachoir.parser import createParser
from hachoir.metadata import extractMetadata



def creation_date(filename):
    parser = createParser(filename)
    if not parser:
        return datetime.datetime.max
    try:
        metadata = extractMetadata(parser)
        if metadata and metadata.has('creation_date'):
            return metadata.get('creation_date').value
    except Exception:
        pass
    finally:
        parser.close()

    return datetime.datetime.max


def get_date():
    """get current date"""
    date = datetime.datetime.now()
    date_today = date.today()
    date_t = (str(date_today.year) + f'{date_today.month:02d}' + f'{date_today.day:02d}')

    return date_t


def renameFiles(file_list, labroll, destination):
    count = 0
    files_ = {}
    print('rename files : ' + labroll)

    for idx, file_path in enumerate(file_list):
        filename = os.path.basename(file_path)
        name, file_extension = os.path.splitext(filename)
        if file_extension.lower() in ['.mp4', '.mov']:
            files_[count] = {}
            files_[count]['origFile'] = file_path
            files_[count]['creationDate'] = creation_date(file_path)
            files_[count]['goproClip'] = name[0:4]
            count += 1

    print(files_)
    res = sorted(files_.items(), key=lambda x: (getitem(x[1], 'creationDate'), getitem(x[1], 'goproClip')))
    print(res)

    try:
        os.mkdir(destination)
    except OSError:
        print("Creation of the directory %s failed" % destination)
    else:
        print("Successfully created the directory %s " % destination)

    index = 0
    this_date = get_date()
    log_file = open(f'{destination}/{labroll}_{get_date()}.log', "w")
    log_file.write(f'### CREATING LABROLL FROM NON-STANDARD CAMROLLS\nStarting at {datetime.datetime.now()}\n\n')

    for element in res:
        print(element[1]["origFile"])
        index += 1
        new_name = f'{labroll[0:4]}C{index:03d}_{this_date}_{labroll[4:]}'
        log_file.write(
            f'[#{index:02d}] {os.path.basename(element[1]["origFile"])} {element[1]["goproClip"]} ({element[1]["creationDate"]}) --> {new_name}.mov\n')
        destination_path = f'{destination}/{new_name}.mov'
        copyfile(element[1]["origFile"], destination_path)

    log_file.write(f'\n### END OF OPERATION at {datetime.datetime.now()}')
    log_file.close()
    return count
