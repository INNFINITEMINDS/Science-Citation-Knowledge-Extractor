from processors import * #pyProcessors
import os.path, time, re, logging, pickle, json, codecs, arrow
from itertools import chain #for "flatten" function
from database_management import * #mine
from Entrez_IR import * #mine
from multi_preprocess import * #mine
from lsa1 import * #mine
from lda1 import * #mine
from fasttext import * #mine
from fgraph import *
from journalvis import * #mine
from nes import * #mine
from kmeans1 import * #mine
from naive_cosineSim import * #mine
from fgraph2json import embedding_json #mine



## Supporting functions for app.py

################## LOGGING #######################################################

#Create log
logging.basicConfig(filename='.app.log',level=logging.DEBUG)
logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

############# PROCESSORS SERVER ##################################################

#Set a PROCESSORS_SERVER environment variable.
#It may take a minute or so to load the large model files.
def connect_to_Processors(port_num):
  path = '/home/hclent/anaconda3/envs/py34/lib/python3.4/site-packages/processors/processors-server.jar'
  api = ProcessorsAPI(port=port_num, jar_path=path, keep_alive=True, jvm_mem="-Xmx25G")
  logging.info('Connected to pyProcessors')
  #Initialize the bionlp annotator by passing it a doc
  init_doc = api.bionlp.annotate("The mitochondria is the powerhouse of the cell.")
  return api


#TODO: Possibly load FastText model as global variable?

################### INPUT #########################################################

#User can enter in as many pubmed ids as they want into text box
#This method creates a list of them
def multiple_pmid_input(user_input):
	logging.info('cleaning user input')
	clean = re.sub('\,', ' ', user_input)
	ids = clean.split() #list of pmids
	return ids

################### DATABASE #####################################################
#If the pmid is NOT in the db, we also need to getSelfText and write that info to db
def scrape_and_write_Input(user_input):
	logging.info('retrieve Self text, and write to db')
	self_pmcid, self_abstract_check, self_article_check = getSelfText(user_input) #Entrez_IR function
	logging.info("PMICD: ")
	logging.info(self_pmcid)
	updateInputPapers(user_input, self_pmcid, self_abstract_check, self_article_check)  # put getSelfText into database

#input: user_input pmid
#output: list of dicts with annotation checks [{"pmcid": 123, "annotated": yes}]
def annotation_check(user_input):
	a_check = []
	pmc_ids = db_citation_pmc_ids(user_input) #Used to use getCitationIDs(user_input) here but updated to using my own db
	for citation in pmc_ids:
		#print(citation)
		annotationDict = {"pmcid": citation, "annotated": []}

		prefix = '/home/hclent/data/pmcids/' + str(citation[0:3])  # folder for first 3 digits of pmcid
		suffix = prefix + '/' + str(citation[3:6])  # folder for second 3 digits of pmcid nested in prefix
		filename = suffix + '/' + str(citation) + '.json'
		with open(filename) as data_file:
			data = json.load(data_file)
			if "error annotating document" in data["text"][:25]:
				annotationDict["annotated"].append("no")
			else:
				annotationDict["annotated"].append("yes")

		a_check.append(annotationDict)
	return a_check

#Used by both IR_not_in_db and IR_in_db to 1) add new pmcids to cited db and 2) duplicate entries when necessary
#Input is the "citation" (dict) result of the result "allCitationsInfo = getCitedInfo(pmc_ids, user_input)" in for loop
#Updated to sqlalchemy
def new_or_copy_db(citation): #citation is a dict
	if "annotated" in citation:
		logging.info("this entry has already been annotated before. just copy.")
		date = str(arrow.now().format('YYYY-MM-DD'))
		pmcid = citation["pmcid"]
		title = str(citation["pmc_titles"][0])
		author = str(citation["pmc_authors"][0])
		journal = str(citation["pmc_journals"][0])
		pubdate = str(citation["pmc_dates"][0])
		citesPmid = str(citation["citesPmid"])
		url = str(citation["pmc_urls"][0])
		abstract = str(citation["abstract_check"][0])
		whole_article = str(citation["article_check"][0])
		sents = str(citation["sents"][0])
		tokens = str(citation["tokens"][0])
		annotated = str(citation["annotated"][0])

		update = citations.insert().\
			values(dict(datestamp = date, pmcid=pmcid, title=title, author=author, journal=journal, pubdate=pubdate,
						citesPmid=citesPmid, url=url, abstract=abstract, whole_article=whole_article, sents=sents,
						tokens=tokens, annotated=annotated ))
		conn.execute(update)

	if "annotated" not in citation:
		logging.info("this entry is brand new, never annotated")
		date = str(arrow.now().format('YYYY-MM-DD'))
		pmcid = str(citation["pmcid"])
		title = str(citation["pmc_titles"][0])
		authorlist = citation["pmc_authors"][0]
		s = ', '
		author = str(s.join(authorlist))
		journal = str(citation["pmc_journals"][0])
		pubdate = str(citation["pmc_dates"][0])
		citesPmid = str(citation["citesPmid"])
		url = str(citation["pmc_urls"][0])

		update = citations.insert().\
			values(dict(datestamp = date, pmcid=pmcid, title=title, author=author, journal=journal, pubdate=pubdate,
						citesPmid=citesPmid, url=url))
		conn.execute(update)






#If pmid (user input) NOT in the db, get main_info AND scrape XML for abstracts and texts
#Write self_info to inputPmids db
#Write allCitationsInfo to citations db
#Update citations db with abstract_check and whole_article_check
#Doesn't re-retrieve information for citations previously scraped (does update db if necessary)
# Updated to sqlalchemy
def run_IR_not_db(user_input):
	logging.info('PMID is NOT in the inputPapers database')
	self_info = getMainInfo(user_input)
	pmc_ids = getCitationIDs(user_input)
	num_citations = len(pmc_ids)
	logging.info("Writing self_info to inputPapers db")
	#write self_info to "inputPapers" db
	for tup in self_info:
		title = tup[0]
		s = ', '
		author = str(s.join(tup[1]))
		journal = tup[2]
		pubdate = tup[3]
		url = tup[4]
		date = str(arrow.now().format('YYYY-MM-DD'))

		update = inputPapers.insert().\
			values(dict(datestamp=date, pmid=user_input, title=title, author=author, journal=journal, pubdate=pubdate,
						url=url, num_citations=num_citations))
		conn.execute(update)

	#Retrieve the input paper if avaliable and update db
	scrape_and_write_Input(user_input)

	#Now retrieve citations
	logging.info("Get basic info about the citations")
	# Previously unseen pmcids only in allCitationsInfo.
	# Previously seen pmcids are copied to db for new pmid in getCitedInfo
	allCitationsInfo = getCitedInfo(pmc_ids, user_input) #output: list of dictionaries [{pmid: 1234, author: human, ...}]
	logging.info("Write basic citation info to citations db")
	for citation in allCitationsInfo:
		logging.info(citation)
		new_or_copy_db(citation)

	#Get content and update citations db
	contentDictList = getContentPMC(pmc_ids, user_input)
	for citation in contentDictList:
		pmcid = str(citation["pmcid"])
		citesPmid = str(citation["citesPmid"])
		abstract = str(citation["all_abstract_check"][0])
		whole_article = str(citation["all_article_check"][0])

		up = citations.update().\
			where(citations.c.pmcid == pmcid).\
			where(citations.c.citesPmid == citesPmid).\
			values(dict(abstract=abstract, whole_article=whole_article))
		conn.execute(up)


# If pmid (user input) in the inputPapers database, check for new papers
# If ther are new citing papers, get those and update the db appropriately
# Else if there are no new papers, don't need to do anything.
# Updated to sqlalchemy
def run_IR_in_db(user_input):
	logging.info('PMID is in the database')
	# Check for new papers:
	num_in_db = db_input_citations_count(user_input) #checks MY db
	pmc_ids = getCitationIDs(user_input) #checks ENTREZ DB
	num_current = len(pmc_ids)
	#If there are new papers,
	if num_current == num_in_db: #TODO change this back to > after i've fixed authors problem
		need_to_annotate = 'yes'
		#print("there are new citations!", (num_current, num_in_db))
		#update number of citations in inputPaper db

		update = inputPapers.update().\
			where(inputPapers.c.pmid == user_input).\
			values(num_citations=num_current)
		conn.execute(update)

		#now get the new citation info
		allCitationsInfo = getCitedInfo(pmc_ids, user_input)  # output: list of dictionaries [{pmid: 1234, author: human, ...}] #skips duplicates
		logging.info("Write basic citation info to citations db for new papers")
		for citation in allCitationsInfo:
			new_or_copy_db(citation)

		#Get content and update citations db
		logging.info("now get the content for the new stuff")
		contentDictList = getContentPMC(pmc_ids, user_input)
		for citation in contentDictList:
			pmcid = str(citation["pmcid"])
			citesPmid = str(citation["citesPmid"])
			abstract = str(citation["all_abstract_check"][0])
			whole_article = str(citation["all_article_check"][0])

			up = citations.update().\
				where(citations.c.pmcid == pmcid).\
				where(citations.c.citesPmid == citesPmid).\
				values(dict(abstract=abstract, whole_article=whole_article))
			conn.execute(up)

	else:
		logging.info("no new papers, nothing to do here folks")
		need_to_annotate = 'no'
		pass
	return need_to_annotate





def new_citations_from_db(user_input):
	apa_citations, db_journals, db_dates, db_urls = db_citations_retrieval(user_input)
	return apa_citations, db_urls
	#apa_citations called 'main' in app.py


#Data for populating statistics page in app
def get_statistics(pmid_list):
	total = []
	unique_pmcids = []
	all_abstracts = []
	all_whole = []
	all_sents = []
	all_tokens = []
	for pmid in pmid_list:
		pmidDict, pmcDict = db_statistics(pmid)
		#print(pmidDict)
		total.append(pmidDict[pmid])
		#print(pmcDict)
		for key, value in pmcDict.items():
			if key not in unique_pmcids:
				unique_pmcids.append(key)
			abstract = value[0]
			if abstract == 'yes':
				all_abstracts.append(abstract)
			whole = value[1]
			if abstract == 'yes':
				all_whole.append(whole)
			sent = value[2]
			if isinstance(sent, int):
				all_sents.append(sent)
			token = value[3]
			if isinstance(token, int):
				all_tokens.append(token)
	sum_total = sum(total)
	unique = (len(unique_pmcids))
	sum_abstracts = len(all_abstracts)
	sum_whole = len(all_whole)
	sum_sents = sum(all_sents)
	sum_tokens = sum(all_tokens)
	statistics = [sum_total, unique, sum_abstracts, sum_whole, sum_sents, sum_tokens]
	#print(statistics)
	return statistics



#use query to get info about input papers
def statsSelfInfo(query):
    input_click_citations = []
    pmid_list = query.split('+')  # list of string pmids
    for user_input in pmid_list:
        apa = db_inputPapers_retrieval(user_input)
        url = "https://www.ncbi.nlm.nih.gov/pubmed/"+str(user_input)
        href_label = (apa, url) #store apa and url as a tuple
        input_click_citations.append(href_label) #then append to list
    return(input_click_citations)


#take a query and generate x and y datapoints for pubs x year bar chart in "Stats" tab
#TODO: sepperate counts (have a different bar) for each inputPaper
def stats_barchart(query):
	pmid_list = query.split('+') #list of string pmids
	journals = []
	dates = []
	for user_input in pmid_list:
		apa_citations, db_journals, db_dates, db_urls = db_citations_retrieval(user_input)
		for j in db_journals:
			journals.append(j)
		for d in db_dates:
			dates.append(d)
	x, y = paper_dates_barchart(journals, dates, query)
	return x, y


############ DATA VISUALIZATIONS #################################################
#Updated to SqlAlchemy
#TODO: no mechanism for updating db if more citations have been found!!
def print_journalvis(query):
	record = checkForQuery(query)  # check for query in db.
	logging.info("checked for query!!!")
	logging.info(record)
	if record == 'empty':
		#if the record has never been seen before, do the journalsvis and write to db
		years_range = get_years_range(query) #need range for ALL journals, not just last one
		logging.info(years_range)
		publication_data, range_info = journals_vis(years_range, query) #range info = [('2008', '2016'), 165, 48]
		logging.info(range_info)
		journal_years = range_info[0]
		logging.info(journal_years)
		q = '+'
		logging.info(q)
		range_years = str(q.join(journal_years))
		logging.info("range years: "+range_years)
		unique_publications = range_info[1]
		unique_journals = range_info[2]
		logging.info(range_info)
		logging.info('Printing JOURNALS to JSON')
		save_path = '/home/hclent/data/journals/' #save in journals folder
		completeName = os.path.join(save_path, ('journals_'+(str(query))+'.json')) #named after query
		with open(completeName, 'w') as outfile:
			json.dump(publication_data, outfile)
		date = str(arrow.now().format('YYYY-MM-DD'))

		update = queries.insert().\
			values(dict(datestamp=date, query=query, range_years=range_years, unique_pubs=unique_publications,
						unique_journals=unique_journals))
		conn.execute(update)


	if record == 'yes': #if its in the db, just get the important things from the db!!
		range_years, unique_publications, unique_journals = getJournalsVis(query)
	return range_years, unique_publications, unique_journals




def vis_wordcloud(neslist, nes_categories, w_number):
	nesDict = frequency_dict(neslist, nes_categories)
	#print(nesDict)
	wcl = wordcloud(nesDict, int(w_number))
	#print(wcl)
	return wcl

#TODO: word counts for documents seem to have some mistakes. Look into this!!!
def vis_heatmap(data_samples, neslist, nes_categories, w_number):
	nesDict = frequency_dict(neslist, nes_categories)
	x_docs, y_words, z_counts  = doHeatmap(nesDict, w_number, data_samples)
	return x_docs, y_words, z_counts

#for getting heatmap titles
#TODO: word counts for documents seem to have some mistakes. Look into this!!!
def vis_heatmapTitles(query):
	titles = []  # want citations instead of titles
	pmid_list = query.split('+')  # list of string pmids
	for pmid in pmid_list:
		temp_titles = db_citations_hyperlink_retrieval(pmid)  # return apa citation hyperlink for click data
		for t in temp_titles:  #
			titles.append(t)
	return titles

#TODO: fix papers axis so its not smooshed together and ugly
def vis_clustermap(data_samples, nes_list, nes_categories, w_number, query):
	logging.info("starting clustermap")
	x, y, z = vis_heatmap(data_samples, nes_list, nes_categories, w_number)
	logging.info("making clustermap data")
	seaData = make_seaborn_data(x, y, z)
	logging.info("saving clustermap png")
	saveName = makeClusterMap(seaData, query)
	return saveName #return filename


def vis_kmeans(data_samples, num_clusters, pmid_list):
	#use query to get titles
	titles = [] #want citations instead of titles
	for pmid in pmid_list:
		#temp_titles = db_citation_titles(pmid)
		temp_titles = db_citations_hyperlink_retrieval(pmid) #return apa citation hyperlink for click data
		for t in temp_titles: #
			titles.append(t)

	hX, hasher = get_hashing(data_samples)
	clusters = do_kemeans(hX, int(num_clusters)) #list of cluster assignments
	coordinates = do_NMF(hX) #dimensionality reduction for visualization
	#zip coordinates and titles
	zipped_coordinates = zip(coordinates, titles)
	x0_coordinates, y0_coordinates, z0_coordinates, x1_coordinates, y1_coordinates, z1_coordinates, x2_coordinates, y2_coordinates, z2_coordinates, x3_coordinates, y3_coordinates, z3_coordinates, x4_coordinates, y4_coordinates, z4_coordinates, titles0, titles1, titles2, titles3, titles4 = plotKmeans(zipped_coordinates, clusters) #format for Plotly scatterplot
	return x0_coordinates, y0_coordinates, z0_coordinates, x1_coordinates, y1_coordinates, z1_coordinates, x2_coordinates, y2_coordinates, z2_coordinates, x3_coordinates, y3_coordinates, z3_coordinates, x4_coordinates, y4_coordinates, z4_coordinates, titles0, titles1, titles2, titles3, titles4


#scifi visualization
#are query papers eligible to be loaded as a corpus?
#first pass: check to see if the self_ text exists
#later on can check databse instead.
def inputEligible(query):
	papers = []
	values = ['paper1', 'paper2', 'paper3', 'paper4', 'paper5']
	path_to_paper = []
	pmid_list = query.split('+')  # list of string pmids
	for pmid in pmid_list:
		pmcid = pmid2pmcid(pmid)
		if pmcid != "NA":
			#print(pmcid)
			#print(pmid + " = " + pmcid)
			#get the pmcid of the pmid

			prefix = pmcid[0:3]
			suffix = pmcid[3:6]
			filename = '/home/hclent/data/pmcids/' + str(prefix) + '/' + str(suffix) + '/' + str(pmcid) + '.txt' # look in folder that matches pmcid
			#print(filename)
			truth_value = os.path.isfile(filename)
			if truth_value is True:
				#print(filename) #NA won't exist
				papers.append(pmid)
				path_to_paper.append(filename)
	eligible_papers = list(zip(values, papers, path_to_paper))
	return eligible_papers


#visualization for scifi div
# TODO: make hyperlinks https
def vis_scifi(corpus, query, eligible_papers):
	corpus_vec, color = load_corpus(corpus, eligible_papers)
	eligible_cosines = get_cosine_eligible(corpus_vec, eligible_papers)
	data_vecs_list = load_datasamples(query)
	cosine_list = get_cosine_list(corpus_vec, data_vecs_list)
	sorted_combos = add_urls(query, cosine_list, color)
	all_sorted_combos = add_eligible_cosines(sorted_combos, eligible_papers, eligible_cosines)
	x, y, names, color_list = prepare_for_histogram(all_sorted_combos)
	return x, y, names, color_list

############ PROCESSING BIODOCS ############################################
#Take pmcid.txt and get an annotated document, as well as lemmas and named entities
#Doesn't re-annotated documents that have already been annotated.
#Updated to sqlalchemy
def do_multi_preprocessing(user_input):
	logging.info('Beginning multiprocessing for NEW (unprocessed) docs')
	t1 = time.time()
	docs = retrieveDocs(user_input)
	multiprocess(docs) #if docs is empty [], this function just passes :)
	# # #Now update annotated_check
	a_check = annotation_check(user_input)

	for a in a_check: #{"pmcid": pmcid, "annotated": ['yes']}
		pmcid = str(a["pmcid"])
		annotated = str(a["annotated"][0])

		update = citations.update().\
			where(citations.c.pmcid == pmcid).\
			where(citations.c.citesPmid == user_input).\
			values(annotated=annotated)
		conn.execute(update)

	#Now extract information from annotated documents
	biodocs = retrieveBioDocs(user_input)
	biodoc_data = loadBioDoc(biodocs) #list of dictionaries[{pmid, lemmas, nes, sent_count, token_count}]
	#No problem getting biodocs or biodoc_data ... problem comes with updating db...
	#update db with sents and tokens
	for b in biodoc_data:
		update_annotations(b, user_input)
	logging.info("Execute everything: done in %0.3fs." % (time.time() - t1))
	return biodoc_data

#Revamped data_samples caching function
#Old method: save a pickled list of lists for each query
#New method:
'''Going to save a dictionary of {citing pmcid: ['the text']} for each pmid, named "data_samples_<pmid>.pickle"
   Save this as a pickle in a super nested directory (for speed), like what I do with annotated Biodocs.
   Then to get the data_samples list of lists, I will concatenate the dictionaries and pull out only the set() to get just the unique items
   (no repeats).
   Then will convert this to the list of lists, (and make a list of the pmcids_list)

   Also will do the same for nes_samples :)
 '''
def print_data_samples(user_input, biodoc_data):
	logging.info("printing datasamples... ")

	prefix = '/home/hclent/data/pmid_ds/' + str(user_input[0:3])  # folder for first 3 digits of pmcid
	suffix = prefix + '/' + str(user_input[3:6])  # folder for second 3 digits of pmcid nested in prefix

	try:
		os.makedirs(prefix)  # creates folder named after first 3 digits of pmcid
	except OSError:
		if os.path.isdir(prefix):
			pass
		else:
			raise

	try:
		os.makedirs(suffix)  # creates folder named after second 3 digits of pmicd
	except OSError:
		if os.path.isdir(suffix):
			pass
		else:
			raise

	data_completeName = os.path.join(suffix, ('data_samples_' + (str(user_input)) + '.pickle'))
	logging.info(data_completeName)
	pickle.dump(biodoc_data, open( data_completeName , "wb"))
	logging.info("data_samples dumped to pickle")



def biodoc2data(query):
	pmid_list = query.split('+')  # list of string pmids

	all_pmcids = []
	all_lemma_samples = []
	all_nes_samples = []
	for pmid in pmid_list:
		filename = '/home/hclent/data/pmid_ds/' + str(pmid[0:3])  + '/' + str(pmid[3:6]) + '/' +'data_samples_' + (str(pmid)) + '.pickle'
		print(filename)
		with open(filename, 'rb') as f:
			list_of_biodicts = pickle.load(f)
		for biodict in list_of_biodicts:
			pmcid = biodict["pmcid"]
			all_pmcids.append(pmcid)
			lemmas = biodict["lemmas"]
			all_lemma_samples.append(lemmas)
			nes = biodict["nes"]
			all_nes_samples.append(nes)
	#get unique pmcids so no repeats
	pmcids_set = set(all_pmcids)
	pmcids = [p for p in pmcids_set]

	lemma_samples_set = [list(x) for x in set(tuple(x) for x in all_lemma_samples)]
	lemma_samples = [ds for ds in lemma_samples_set]

	# nes_set = [list(n) for n in set(tuple(n) for n in all_nes_samples)] #n in all_nes_samples is a list of dictionaries
	# nes_samples = [ns for ns in nes_samples]

	print("###### ALL ########")
	print(len(all_pmcids))
	print(len(all_lemma_samples))
	print(len(all_nes_samples))
	print('######## UNIQUE #########')
	print(len(pmcids))
	print(len(lemma_samples))

	print(all_nes_samples[0])



#biodoc2data('18952863+18269575')


############ TOPIC MODELING ############################################
def run_lsa1(data_samples, k):
	logging.info('Beginning Latent Semantic Analysis')
	tfidf, tfidf_vectorizer = get_tfidf(data_samples)
	jsonDict = do_LSA(tfidf, tfidf_vectorizer, k) #need to make this an option
	return jsonDict


def run_lda1(data_samples, num_topics, n_top_words): #set at defulat k=3, number of words=5
	logging.info('Beginning Latent Dirichlet Allocation')
	tfidf, tfidf_vectorizer = get_tfidf(data_samples)
	lda = fit_lda(tfidf, num_topics)
	jsonLDA = topics_lda(tfidf_vectorizer, lda, n_top_words)
	return jsonLDA


#Input: query, top N desired bin, k clusters
#Output: prints csv for force directed graph
def run_embeddings(query, top_n, k_clusters):
	logging.info("in run_embeddings function")#
	pmid_list = query.split('+')  # list of string pmids
	words, tags = get_words_tags(pmid_list) #list of words/tags per doc
	transformed_sentence = transform_text(words, tags)
	npDict = chooseTopNPs(transformed_sentence)
	logging.info("done with npDict")
	logging.info(type(top_n))
	logging.info(type(k_clusters))
	if top_n == 100:
		logging.info("w=1-100")
		top = list(npDict.most_common(top_n))
	elif top_n == 200:
		logging.info("w=101-200")
		top_nps100 = list(npDict.most_common(100))
		top_nps200 = list(npDict.most_common(200))
		top = [item for item in top_nps200  if item not in top_nps100]
	elif top_n == 300:
		logging.info("w=201-300")
		top_nps200 = list(npDict.most_common(200))
		top_nps300 = list(npDict.most_common(300))
		top = [item for item in top_nps300  if item not in top_nps200]
	elif top_n == 400:
		logging.info("w=301-400")
		top_nps300 = list(npDict.most_common(300))
		top_nps400 = list(npDict.most_common(400))
		top = [item for item in top_nps400  if item not in top_nps300]
	else:
		top = list(npDict.most_common(top_n))
	logging.info("done with top NPs")
	model = load_model('/home/hclent/tmp/fastText/16kmodel.vec')
	logging.info("loaded model all the way!")
	matrix = getNPvecs(top, model)
	logging.info("getting the matrix!")
	kmeans = KMeans(n_clusters=k_clusters, random_state=2).fit(matrix)
	results = list(zip(kmeans.labels_, top))
	embedding_json(results, query)
	logging.info("made json for embedding topic model")
	'''depreciated CSV'''
	#val_matrix = make_matrix(results, model)
	#make_csv(val_matrix, results, query)



########### WRITING TO JSON / PICKLE ###############################################

def print_lsa(query, user_input, jsonDict):
	#Save the json for @app.route('/reslsa/')
	logging.info('Printing LSA to JSON')
	save_path = '/home/hclent/data/topics/lsa' #in the folder of the last pmid
	completeName = os.path.join(save_path, ('lsa_'+(str(query))+'.json')) #with the query for a name
	with open(completeName, 'w') as outfile:
		json.dump(jsonDict, outfile)

def print_lda(query, user_input, jsonLDA):
	#Save the json for @app.route('/reslda/')
	logging.info('Printing LDA to JSON')
	save_path = '/home/hclent/data/topics/lda' #in the folder of the last pmid
	completeName = os.path.join(save_path, ('lda_'+(str(query))+'.json'))  #with the query for a name
	with open(completeName, 'w') as outfile:
		json.dump(jsonLDA, outfile)


def flatten(listOfLists):
    return list(chain.from_iterable(listOfLists))

#Input: the output of do_multi_preprocessing (list of dicts with lemmas and named entities)
#This function stores selected information about the annotation in the db table 'annotations'
#Ooutput: none
#Updated to sqlalchemy
#TODO: I don't think this is super helpful... better to just cache pickle files
def biodoc_to_db(biodoc_data):
	for biodict in biodoc_data:
		pmcid = str(biodict["pmcid"])
		record = annotationsCheckPmcid(pmcid)
		# step 1: if pmcid already in db, pass
		if record == 'yes':
			logging.info("repeat!")
			pass
		# step 2: if pmcid not in db, add the things!
		if record == 'empty':
			lemmas = str(biodict["lemmas"]) #will be a string that looks like a list... will have to parse back into list somehow
			logging.info(lemmas)
			all_nes = biodict["nes"][0] #its a list with one dictionary in it (hence we index [0] to get the dict)
			try:
				bioprocess_list = all_nes["BioProcess"]
				#['translation', 'homeostasis', 'stress response', 'stress response'] #will need to make a string
				#String where we can put it back in a list!
				bioprocess = ", ".join(bioprocess_list) #translation, homeostasis, stress response, stress response
			except Exception as e1:
				bioprocess = '' #empty string
			try:
				cell_lines = ", ".join(all_nes["CellLine"])
			except Exception as e2:
				cell_lines = ''
			try:
				cell_components = ", ".join(all_nes["Cellular_component"])
			except Exception as e3:
				cell_components = ''
			try:
				family = ", ".join(all_nes["Family"])
			except Exception as e4:
				family = ''
			try:
				gene_product = ", ".join(all_nes["Gene_or_gene_product"])
			except Exception as e5:
				gene_product = ''
			try:
				organ = ", ".join(all_nes["Organ"])
			except Exception as e6:
				organ = ''
			try:
				simple_chemical = ", ".join(all_nes["Simple_chemical"])
			except Exception as e7:
				simple_chemical = ''
			try:
				site = ", ".join(all_nes["Site"])
			except Exception as e8:
				site = ''
			try:
				species = ", ".join(all_nes["Species"])
			except Exception as e9:
				species = ''
			try:
				tissue_type = ", ".join(all_nes["TissueType"])
			except Exception as e10:
				tissue_type = ''
			date = str(arrow.now().format('YYYY-MM-DD'))

			update = annotations.insert().\
				values(dict(datestamp=date, pmcid=pmcid, lemmas=lemmas, bioprocess=bioprocess, cell_lines=cell_lines, cell_components=cell_components,
							family=family, gene_product=gene_product, organ=organ, simple_chemical=simple_chemical, site=site, species=species,
							tissue_type=tissue_type))
			conn.execute(update)


############## GRAVEYARD ##########################################################
