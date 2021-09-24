# Comprehensive-Manga-Downloader
This is a python based crawler that allows you to search and download manga of any anime (any chapter). This crawls http://www8.mangafreak.net
## Install Dependencies
`pip3 install selenium fpdf`
`pip3 install pillow`

Execute the script by using `python go.py`


Execute the script:

![screenshot from 2018-07-04 10-17-25](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_1.PNG)

Enter Anime name to be searched:

![screenshot from 2018-07-04 10-18-04](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_2.PNG)

Anime Search Results:

![screenshot from 2018-07-04 10-18-04](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_3.PNG)

Choose the index from the results

![screenshot from 2018-07-04 10-18-04](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_4.PNG)

Select the chapter or press zero for a range of chapters. 

![screenshot from 2018-07-04 10-19-06](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_5.PNG)

Script will download the zips to extract and convert them run the following script.
`python images_to_pdf.py`

Enter the Subname of ZipFiles.
(for eg : `Mairimashita_Iruma_Kun` from `Mairimashita_Iruma_Kun_100.zip`

Finally The zips will unzipped and be converted into respective PDFs and stored in a new folder in present Directory
![screenshot from 2018-07-04 10-19-51](https://github.com/Akshat69/Manga-Downloader-Mangafreak-/blob/main/Capture_9.PNG)

Enjoy Reading your Favourite Manga :))))))))
