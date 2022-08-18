from wand.image import Image


# simple image compare algorithm
def adjusted_compare_with_trim(first, second, trim):
    # the main idea is to perform a series of tests where if inconclusive, we move on to a different test
    # first, we just do a general sweep. If the percent match is too high or too low, we return the result
    # then, we perform a test on the image if it is cropped upwards
    # then, we perform a test on the image if it is cropped downards
    # then, if the image needs to be trimmed, we run it through again with the trimmed variant
    # then, if all of the tests are inconclusive, we return the max value returned

    # resize the images to a reasonable amount
    if trim is not None:
        comparison = exact_compare_with_trim(first, second, trim)
    else:
        comparison = exact_compare(first, second)

    if comparison < 50 or comparison > 97:
        return comparison

    with Image(filename=first) as first_img, Image(filename=second) as second_img:
        first_img.normalize()
        second_img.normalize()

        # resize the images to a reasonable amount
        first_img.resize(32, 32)
        second_img.resize(32, 32)

        comparison = 100 * first_img.compare(second_img, metric='undefined')[1]

        if comparison < 80 or comparison > 97.5:
            return comparison

        # when we crop, we will want the image to be larger (more precise cuts)
        first_img.resize(1200, 1200)
        second_img.resize(1200, 1200)

        # now we check if the image is cropped upwards
        try:
            with first_img[0: int(first_img.width), 0: int(first_img.height)] as first_chunk:
                first_chunk.save(filename='/tmp/first_sample.jpg')
            with second_img[0: int(second_img.width), 0: int(second_img.height * .9)] as second_chunk:
                second_chunk.save(filename='/tmp/second_sample.jpg')

            with Image(filename="/tmp/first_sample.jpg") as first_chunk_img, \
                    Image(filename="/tmp/second_sample.jpg") as second_chunk_img:
                first_chunk_img.resize(64, 64)
                second_chunk_img.resize(64, 64)

                result = first_chunk_img.compare(second_chunk_img, metric='undefined')[1] * 100
        except IndexError:
            result = 0

        if result > 97 or 65 < result < 80:
            return result

        # now we check if the web-ID image is cropped upwards
        try:
            with first_img[0: int(first_img.width), 0: int(first_img.height * .9)] as chunk:
                chunk.save(filename='/tmp/first_sample.jpg')
            with second_img[0: int(second_img.width), 0: int(second_img.height)] as second_chunk:
                second_chunk.save(filename='/tmp/second_sample.jpg')

            with Image(filename="/tmp/first_sample.jpg") as first_chunk_img, \
                    Image(filename="/tmp/second_sample.jpg") as second_chunk_img:
                first_chunk_img.resize(64, 64)
                second_chunk_img.resize(64, 64)

                result = first_chunk_img.compare(second_chunk_img, metric='undefined')[1] * 100
        except IndexError:
            result = 0

        # if the result is in the goldilocks zone, we return it
        if result > 97 or 65 < result < 80:
            return result

        # now we crop from the bottom up
        try:
            with first_img[0: int(first_img.width), 0: int(first_img.height)] as chunk:
                chunk.save(filename='/tmp/first_sample.jpg')
            with second_img[0: int(second_img.width), int(second_img.height * .1): int(second_img.height)] as second_chunk:
                second_chunk.save(filename='/tmp/second_sample.jpg')

            with Image(filename="/tmp/first_sample.jpg") as first_chunk_img, \
                    Image(filename="/tmp/second_sample.jpg") as second_chunk_img:
                first_chunk_img.resize(64, 64)
                second_chunk_img.resize(64, 64)

                result = first_chunk_img.compare(second_chunk_img, metric='undefined')[1] * 100
        except IndexError:
            result = 0

        if result > 97 or 65 < result < 80:
            return result

        # next we crop horizontally
        try:
            with first_img[int(first_img.width * .25): int(first_img.width * .75), 0: int(first_img.height)] as chunk:
                chunk.save(filename='/tmp/first_sample.jpg')
            with second_img[int(second_img.width * .25): int(second_img.width * .75), 0: int(second_img.height)] as second_chunk:
                second_chunk.save(filename='/tmp/second_sample.jpg')

            with Image(filename="/tmp/first_sample.jpg") as first_chunk_img, \
                    Image(filename="/tmp/second_sample.jpg") as second_chunk_img:
                first_chunk_img.resize(64, 64)
                second_chunk_img.resize(64, 64)

                result = first_chunk_img.compare(second_chunk_img, metric='undefined')[1] * 100
        except IndexError:
            result = 0

        if result > 97 or 65 < result < 75:
            return result

    with Image(filename=first) as first_img, Image(filename=second) as second_img:
        first_img.normalize()
        second_img.normalize()

        first_img.resize(1200, 1200)
        second_img.resize(1200, 1200)

        # return the bigger value of the two
        current = 100 - 100 * first_img.compare(second_img, metric='mean_squared')[1]
        other_current = 100 * first_img.compare(second_img, metric='undefined')[1]
        if current < other_current:
            min_val = current
        else:
            min_val = other_current

        mid_val = 0
        in_range = False

        if abs(current - other_current) < 12 and min_val < 88:
            mid_val = (current + other_current) / 2
            in_range = True

        if current > other_current:
            if in_range:
                return (current + mid_val) / 2
            else:
                return current
        else:
            if in_range:
                return (other_current + mid_val) / 2
            else:
                return current


def adjusted_compare(first, second):
    return adjusted_compare_with_trim(first, second, None)
    

def exact_compare_with_trim(first, second, trim):
    trim_fuzz = int(trim)

    with Image(filename=first) as first_img:
        first_img.trim(first_img[0, 0], trim_fuzz)
        first_height = 400 if first_img.height > 400 else first_img.height
        first_width = first_height * first_img.width / first_img.height
        first_img.resize(first_width, first_height, 'undefined', 1)
        first_img.normalize()

        with Image(filename=second) as second_img:
            second_img.trim(second_img[0, 0], trim_fuzz)
            second_img.resize(first_width, first_height, 'undefined', 1)
            second_img.normalize()

            comparison = first_img.compare(second_img, metric='undefined')[1]
            comparison *= 100
    
            return comparison


def exact_compare(first, second):
    return exact_compare_with_trim(first, second, 15000)
