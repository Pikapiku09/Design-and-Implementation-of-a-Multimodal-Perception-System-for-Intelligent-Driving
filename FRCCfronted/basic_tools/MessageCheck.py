from captcha.image import ImageCaptcha
import random,string

def CAPtcha():
    chr_all = string.ascii_letters + string.digits
    chr_4 = ''.join(random.sample(chr_all, 4))
    image = ImageCaptcha().generate_image(chr_4)
    image.save('../basic_img/Message/%s.jpg' % chr_4)
    print(image)

CAPtcha()

