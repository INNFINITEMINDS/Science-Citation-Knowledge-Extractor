from flask import Flask, render_template, request, flash, url_for, redirect, session, g, Blueprint
from flask_wtf import Form
from wtforms import StringField, TextField, SelectField
import sqlite3, gc, time, datetime, pickle, os.path
import sys
from werkzeug.serving import run_simple
sys.path.append('/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/')
from cogeCrawled_db import connection #mine
from content_management import * #mine
from processors import *

#If running in a virtual enviornment, must have modules also (pip) installed in that virtualenv! 
#flask, Flask-WTF, nltk, bs4, lxml, requests, Biopython, pyProcessors


app = Flask(__name__, static_url_path='/hclent/Webdev-for-bioNLP-lit-tool/flask/static')
app.debug = True
app.secret_key = 'super secret key'


#Create Form for handling user-entered pmid
#Need to pass pmid in form to Entrez_IR.py
class pmidForm(Form):
	pmid = TextField('PubmedID')


#Main page
#Prints sample results from 2 coge publications
#User inputs a pubmed id and is then redirected to /results
@app.route("/cogecrawl/")
def cogecrawl():
	error = None
	with open('/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/static/coge_mainfo.pickle', 'rb')as f:
		main_info = pickle.load(f)
	with open('/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/static/coge_nes.pickle', 'rb')as f:
		ner = pickle.load(f)
	with open('/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/static/coge_journals.pickle', 'rb')as f:
		journals = pickle.load(f)
	return render_template("dashboard.html", main_info=main_info, journals=journals, ner=ner)



#Getting Flask-WTFs to work with sqlite3 here
#This function uses user entry to run the Entrez_IR.py 
#User entered pmid is entered into sqlite3 database
@app.route('/results/', methods=["POST"])
def trying():
	logging.info("In app route RESULTS")
	form = pmidForm(secret_key='super secret key')
	try:
		if request.method == 'POST':
			entry = form.pmid.data #THIS IS THE USER INPUT FROM THE FORM #referencing 'class pmidForm'
			pmid_list = multiple_pmid_input(entry) #list for handling multiple pmids
			print(pmid_list)

			q = '+'
			query = str(q.join(pmid_list))
			print("query: " + str(query))

			main_info = []
			target_journals = []
			target_dates = []
			data_samples = []
			ners = []

			for user_input in pmid_list:
				print(str(user_input))
				user_input = str(user_input)

				############################################
				#Connect to database
				conn, c = connection()
				#Check database for pmid #Does the entry exists in the db already?
				c.execute("SELECT * FROM cogeCrawled WHERE pmids = (?)", (user_input, ))
				check1 = c.fetchone()


				#if the entry does NOT exist in the db already, will need to retireve text and annotate
				if check1 is None:
					flash('congrats you entered a new pubmedid lol')
					#Using user_input for Information Retireval of "main info"
					main, journals, dates = run_IR_not_db(user_input)
					for mi in main:
						main_info.append(mi)
					for j in journals:
						target_journals.append(j)
					for d in dates:
						target_dates.append(d)


					data, named_entities = do_ALL_multi_preprocessing(user_input)
					for d in data:
						data_samples.append(d)
					for n in named_entities:
						ners.append(n)


					## Once all the data has been acquired, do topic modeling
					## Only want to save final topic model (not running topic models)
					if user_input == pmid_list[-1]:

						#Do Latent Semantic Analysis and return jsonDict for data vis
						jsonDict = run_lsa1(user_input, data_samples, 2)

						#Do Latent Dirichlet Allocation
						jsonLDA = run_lda1(data_samples, 3, 5)

						print(user_input+" is the last one (JOURNALS")
						print_journalvis(target_journals, target_dates, user_input)
						print(user_input+" is the last one (LSA)")
						print_lsa(user_input, jsonDict) #print lsa topic model to json
						print(user_input+" is the last one (LDA)")
						print_lda(user_input, jsonLDA)

					#add to sqlite3 database entry
					unix = time.time()
					date = str(datetime.datetime.fromtimestamp(unix).strftime('%Y-%m-%d %H: %M: %S'))
					conn, c = connection()
					c.execute("INSERT INTO cogeCrawled (datestamp, pmids) VALUES (?, ?)", (date, user_input)) #put user pmid into db
					conn.commit()
					flash("Writing PubmedID to database: successful")

				#if the entry IS in the db, no need to retireve text from Entrez, just grab
				if check1 is not None:
					flash("alreay exists in database :) ")
					#Using user_input for Information Retireval of "main info"
					main, journals, dates = run_IR_in_db(user_input)
					for mi in main:
						main_info.append(mi)
					for j in journals:
						target_journals.append(j)
					for d in dates:
						target_dates.append(d)

					data, named_entities = do_SOME_multi_preprocessing(user_input)
					for d in data:
						data_samples.append(d)
					for n in named_entities:
						ners.append(n)


					#### errr, if its in the Db, its probably already been topic modeled. so instead should try to load the data,
					## and if can't load the data, do the analysis

					## Now that we have all the data, do the topic model
					## Only want to save final topic model (not running topic model)
					if user_input == pmid_list[-1]:

						# #Do visualization and Topic Modeling
						jsonDict = run_lsa1(user_input, data_samples, 2) #default = 2 "topics" for right now

						#latent dirichlet allocation
						jsonLDA = run_lda1(data_samples, 3, 5)

						logging.info(user_input+" is the last one (JOURNALS)")
						print_journalvis(target_journals, target_dates, user_input)
						print(user_input+" is the last one (LSA)")
						print_lsa(user_input, jsonDict) #print lsa topic model to json
						print(user_input+" is the last one (LDA)")
						print_lda(user_input, jsonLDA)


				#End cursor and connection to database
				c.close()
				conn.close()


				#Housekeeping
				gc.collect() #garbage collector for cleaning up unneeded stuff
				session['entered_id'] = True
				session['engaged'] = 'engaged'

		return render_template('results.html', form=form, main_info = main_info, target_journals = target_journals, ners=ners, query=query)


	except Exception as e:
		return(str(e))


#Create Form for handling visualization options
class visOptions(Form):
	k_val = SelectField('k_val', choices=[(2,'k=2'),(3,'k=3'),(4,'k=4'),(5,'k=5')])
	w_words = SelectField('w_words', choices=[(4, 'w=4'),(5, 'w=5'),(6, 'w=6'), (7, 'w=7') ])



class stooopid(Form):
	k_val = SelectField('k_val', choices=[(2,'k=2'),(3,'k=3'),(4,'k=4'),(5,'k=5')])
	w_words = SelectField('w_words', choices=[(4, 'w=4'),(5, 'w=5'),(6, 'w=6'), (7, 'w=7') ])


################ Routes for visualization toggle ################


################ Default Coge Data #################
@app.route('/cogelsa/', methods=["GET","POST"]) #default coge lsa for iframe
def cogelsa():
	form = visOptions(secret_key='super secret key')
	if request.method == 'POST':
		k_clusters = form.k_val.data #2,3,4,or 5
		print("the k value is " + str(k_clusters))
		query = '18952863+18269575'
		pmid_list = query.split('+') #list of string pmids
		data_samples = []
		for pmid in pmid_list:
			data, nes = do_SOME_multi_preprocessing(pmid)
			for d in data:
				data_samples.append(d)
		print("rerunning the analysis")
		k = int(k_clusters)
		jsonLSA = run_lsa1(pmid, data_samples, k)
		print("did it all!")
		return render_template('vis_lsa.html', form=form, jsonLSA=jsonLSA) #needs to be parsed
	else: #if nothing is
		completeName = "/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/static/coge_lsa.json"
		with open(completeName) as load_data:
			jsonLSA = json.load(load_data) #doesn't need to be parsed but unsure how to write that in javascript
		#so i'm going to read it in as a string that needs to be parsed anyway
		jsonLSA = re.sub('\'', '\"', str(jsonLSA)) #json needs double quotes, not single quotes
		return render_template('vis_lsa.html', form=form, jsonLSA=jsonLSA)


@app.route('/cogelda/', methods=["GET","POST"]) #default coge lda for iframe
def cogelda():
	form = stooopid(secret_key='super secret key')
	if request.method == 'POST':
		k_clusters = form.k_val.data #2,3,4,or 5
		print("the k value is " + str(k_clusters))
		num_words = form.w_words.data
		print("the w value is "+str(num_words))
		query = '18952863+18269575'
		pmid_list = query.split('+') #list of string pmids
		data_samples = []
		for pmid in pmid_list:
			data, nes = do_SOME_multi_preprocessing(pmid)
			for d in data:
				data_samples.append(d)
		print("rerunning the analysis")
		k = int(k_clusters)
		w = int(num_words)
		jsonLDA = run_lda1(data_samples, k, w)
		return render_template('vis_lda.html', form=form, jsonLDA=jsonLDA)
	else:
		completeName = "/home/hclent/repos/Webdev-for-bioNLP-lit-tool/flask/static/coge_lda1.json"
		with open(completeName) as load_data:
			jsonLDA = json.load(load_data) #doesn't need to be parsed but unsure how to write that in javascript
		#so i'm going to read it in as a string that needs to be parsed anyway
		jsonLDA = re.sub('\'', '\"', str(jsonLDA)) #json needs double quotes, not single quotes
		return render_template('vis_lda.html', form=form, jsonLDA=jsonLDA)


@app.route('/cogejournals/') #default coge journals for iframe
def cogejournals():
	print("in app route /cogejournals/")
	journals = '[{"name": "Nature genetics", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 1], [2016, 0]]}, {"name": "Scientific Reports", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 1]]}, {"name": "Molecular Biology and Evolution", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Frontiers in plant science", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 1], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Journal of Experimental Botany", "total": 3, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 1], [2013, 0], [2014, 1], [2015, 0], [2016, 1]]}, {"name": "Plant and Cell Physiology", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "Frontiers in Genetics", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 2]]}, {"name": "Applied and Environmental Microbiology", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 1]]}, {"name": "Journal of Molecular Evolution", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 2], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "BMC Genomics", "total": 19, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 5], [2014, 9], [2015, 2], [2016, 3]]}, {"name": "PLoS Genetics", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "GigaScience", "total": 3, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 2], [2015, 1], [2016, 0]]}, {"name": "The Plant Cell", "total": 11, "articles": [[2008, 0], [2009, 3], [2010, 0], [2011, 2], [2012, 2], [2013, 1], [2014, 3], [2015, 0], [2016, 0]]}, {"name": "Philosophical Transactions of the Royal Society B: Biological Sciences", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "Proceedings of the National Academy of Sciences of the United States of America", "total": 3, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 2], [2013, 1], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Parasites & Vectors", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 1], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Frontiers in Neuroscience", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 1], [2016, 0]]}, {"name": "Genetics", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 1], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "BMC Evolutionary Biology", "total": 6, "articles": [[2008, 0], [2009, 0], [2010, 1], [2011, 2], [2012, 0], [2013, 1], [2014, 0], [2015, 1], [2016, 1]]}, {"name": "BMC Genetics", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "BMC Bioinformatics", "total": 8, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 1], [2012, 3], [2013, 4], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Genome Biology and Evolution", "total": 6, "articles": [[2008, 0], [2009, 1], [2010, 0], [2011, 1], [2012, 0], [2013, 3], [2014, 0], [2015, 1], [2016, 0]]}, {"name": "Nature", "total": 1, "articles": [[2008, 1], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Annals of Botany", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 1], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "International Journal of Molecular Sciences", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "Nucleic Acids Research", "total": 8, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 3], [2012, 3], [2013, 0], [2014, 2], [2015, 0], [2016, 0]]}, {"name": "Plant Biotechnology Reports", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "PLoS ONE", "total": 16, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 2], [2012, 4], [2013, 1], [2014, 4], [2015, 3], [2016, 2]]}, {"name": "BioMed Research International", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 1]]}, {"name": "PLoS Biology", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 2], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Molecular Genetics and Genomics", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 1]]}, {"name": "The Plant journal : for cell and molecular biology", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 2], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Plant Physiology", "total": 3, "articles": [[2008, 1], [2009, 0], [2010, 0], [2011, 1], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "The ISME Journal", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "G3: Genes|Genomes|Genetics", "total": 3, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 2], [2015, 0], [2016, 0]]}, {"name": "Mobile Genetic Elements", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 1], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Genome Research", "total": 2, "articles": [[2008, 2], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Genes & Development", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 1], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "BMC Plant Biology", "total": 6, "articles": [[2008, 0], [2009, 0], [2010, 2], [2011, 1], [2012, 0], [2013, 0], [2014, 2], [2015, 1], [2016, 0]]}, {"name": "Genome Biology", "total": 2, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 1], [2012, 1], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "Frontiers in Plant Science", "total": 18, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 1], [2012, 3], [2013, 2], [2014, 1], [2015, 6], [2016, 5]]}, {"name": "The New Phytologist", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 1], [2014, 0], [2015, 0], [2016, 0]]}, {"name": "PeerJ", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 1], [2016, 0]]}, {"name": "Plant Molecular Biology Reporter / Ispmb", "total": 1, "articles": [[2008, 0], [2009, 0], [2010, 0], [2011, 0], [2012, 0], [2013, 0], [2014, 1], [2015, 0], [2016, 0]]}, {"name": "Bioinformatics", "total": 3, "articles": [[2008, 0], [2009, 0], [2010, 1], [2011, 0], [2012, 2], [2013, 0], [2014, 0], [2015, 0], [2016, 0]]}]'
	return render_template('journals.html', journals=journals)


############### Results visualizations #############
@app.route('/resjournals/<query>', methods=["GET", "POST"]) #user journals for iframe
def resjournals(query):
	#need to get last user_input
	print("in routine res-journals")
	print("JOURNALS ID: " +str(query))
	#only want to load the json for the LAST id in the query (so includes all)
	pmid_list = query.split('+') #list of string pmids
	last_entry = pmid_list[-1]
	print("the last entry is: " + str(last_entry))
	file_name = "journals_"+str(last_entry)+".json"
	print("last entry's JOURNAL is named: " + str(file_name))
	savePath = "/home/hclent/data/"+str(last_entry)
	completeName = os.path.join(savePath, file_name)
	print("complete file: " + str(completeName))
	with open(completeName) as load_data:
		journals = json.load(load_data)
	print(journals)
	return render_template('results_journals.html', journals = journals)


@app.route('/reslsa/<query>', methods=["GET", "POST"]) #user lsa for iframe
def reslsa(query):
	#need to get last user_input
	#use id to do stuff
	print("in routine resla")
	print("RES-LSA ID: " +str(query))
	#only want to load the json for the LAST id in the query (so includes all)
	pmid_list = query.split('+') #list of string pmids
	last_entry = pmid_list[-1]
	print("the last entry is: " + str(last_entry))
	file_name = "lsa_"+str(last_entry)+".json"
	print("last entry's LSA is named: " + str(file_name))
	savePath = "/home/hclent/data/"+str(last_entry)
	completeName = os.path.join(savePath, file_name)
	print("complete file: " + str(completeName))
	with open(completeName) as load_data:
		jsonDict = json.load(load_data)
	return render_template('results_lsa.html', jsonDict=jsonDict)


@app.route('/reslda/<query>', methods=["GET", "POST"]) #user lsa for iframe
def reslda(query):
	#need to get last user_input
	#use id to do stuff
	print("in routine reslDa")
	print("RES-LDA ID: " +str(query))
	#only want to load the json for the LAST id in the query (so includes all)
	pmid_list = query.split('+') #list of string pmids
	last_entry = pmid_list[-1]
	print("the last entry is: " + str(last_entry))
	file_name = "lda_"+str(last_entry)+".json"
	print("last entry's LDA is named: " + str(file_name))
	savePath = "/home/hclent/data/"+str(last_entry)
	completeName = os.path.join(savePath, file_name)
	print("complete file: " + str(completeName))
	with open(completeName) as load_data:
		jsonLDA = json.load(load_data)
	print(jsonLDA)
	return render_template('results_lda.html', jsonLDA=jsonLDA)



########################################################################

#Handles 404 errors
@app.errorhandler(404)
def page_not_found(e):
	return("you shouldnt be here!!")


#Configuration settings
if __name__ == '__main__':
	run_simple('0.0.0.0', 5000, app, use_reloader=True)
	#app.run(host='0.0.0.0') #dont want app.run() for uwsgi

########### GRAVEYARD ########


