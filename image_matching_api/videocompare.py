import cv2

import compare

FRAMES = {
    'first': 0.05,
    'mid': 0.5,
    'last': 0.95,
}


def extract_frames(video, prefix=''):
    video = cv2.VideoCapture(video)

    if video.isOpened():
        video.read()

    length = video.get(7)

    for frame_name, time in FRAMES.iteritems():
        video.set(1, int(length * time))
        _, image = video.read()
        cv2.imwrite('/tmp/{}_video_{}_frame.jpg'.format(prefix, frame_name), image)  # save frame as JPEG file

    video.release()


def compare_videos(first, second):
    extract_frames(first, prefix='first')
    extract_frames(second, prefix='second')

    result = 0

    for frame_name in FRAMES.keys():
        result += compare.exact_compare('/tmp/{}_video_{}_frame.jpg'.format('first', frame_name),
                                        '/tmp/{}_video_{}_frame.jpg'.format('second', frame_name))

    return result / len(FRAMES.keys())
