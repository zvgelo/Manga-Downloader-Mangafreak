import glob
import zipfile
from PIL import Image
import shutil
import os

folder_name = input("Enter the name of Anime Files to be Converted : ")
if(os.path.isdir(folder_name)):
	shutil.rmtree(folder_name)
os.mkdir(folder_name)
files = glob.glob(f'{folder_name}*.zip')
if(len(files) == 0):
	print("No File found in the Directory!!!!")
	print(quit())

def Images_to_pdf(file):
	zipfile.ZipFile(file).extractall(f"{file.split('.')[0]}")
	destination_folder = file.split('.')[0]
	images_files = os.listdir(destination_folder)
	images_files.sort(key = lambda x : int(x.split("_")[-1].split('.')[0]))
	images = []
	for image_file in images_files:
		image = Image.open(f"{destination_folder}/{image_file}")
		image = image.convert('RGB')
		images.append(image)
	images[0].save(f"{folder_name}/{destination_folder}.pdf",save_all=True, append_images=images)
	print(destination_folder)
	shutil.rmtree(destination_folder)
	os.remove(file)

list(map(Images_to_pdf, files))