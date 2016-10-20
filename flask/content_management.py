from processors import * #pyProcessors
import os.path, time, re, logging, pickle

from database_management import * #mine
from Entrez_IR import * #mine
from multi_preprocess import * #mine
from lsa1 import * #mine
from lda1 import * #mine
from journalvis import * #mine
from nes import * #mine
from kmeans1 import * #mine


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


################### INPUT #########################################################

#User can enter in as many pubmed ids as they want into text box
#This method creates a list of them
def multiple_pmid_input(user_input):
	logging.info('cleaning user input')
	clean = re.sub('\,', ' ', user_input)
	ids = clean.split() #list of pmids
	return ids

################### DATABASE #####################################################
'''
apa_citations will be rendered as 'main' in app.py!!!!
'''


#If pmid (user input) in the inputPapers database,
#get self_info for inputPapers table and
#main_info from citations table
def run_IR_in_db(user_input):
	logging.info('PMID is in the database')
	self_info = db_inputPapers_retrieval(user_input)
	apa_citations, db_journals, db_dates, db_urls = db_citations_retrieval(user_input)
	return self_info, apa_citations, db_journals, db_dates, db_urls


#If pmid (user input) NOT in the db, get main_info AND scrape XML for abstracts and texts
#self_info, main_info, are written to db in app.py
#target_journals and target_dates are used for data vis
def run_IR_not_db(user_input):
	logging.info('PMID is NOT in the database')
	#first run to add things to database
	#self_info is written to the database
	self_info = getMainInfo(user_input)
	pmc_ids = getCitationIDs(user_input)
	num_citations = len(pmc_ids)


	target_title, target_authors, target_journals, target_dates, target_urls = getCitedInfo(pmc_ids)
	#Get content
	all_abstract_check, all_article_check = getContentPMC(user_input, pmc_ids)
	#main_info is written to the database
	new_info = list(zip(pmc_ids, target_title, target_authors,target_journals, target_dates, target_urls, all_abstract_check, all_article_check))

	return self_info, new_info, target_journals, target_dates, num_citations


#
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
            all_sents.append(sent)
            token = value[3]
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




############ DATA VISUALIZATIONS #################################################

def print_journalvis(journals, dates, user_input, query):
	#first, get range:
	years_range = get_years_range(query) #need range for ALL journals, not just last one

	#num_journals = len(journals)
	#print("there are "+str(num_journals)+" journals in total")
	publication_data, range_info = journals_vis(journals, dates, years_range)
	logging.info(publication_data)
	logging.info(range_info)
	logging.info('Printing JOURNALS to JSON')
	save_path = '/home/hclent/data/'+str(user_input)+'/' #save in last pmid folder
	completeName = os.path.join(save_path, ('journals_'+(str(query))+'.json')) #named after query
	with open(completeName, 'w') as outfile:
		json.dump(publication_data, outfile)
	return range_info


def vis_wordcloud(neslist, nes_categories, w_number):
	nesDict = frequency_dict(neslist, nes_categories)
	#print(nesDict)
	wcl = wordcloud(nesDict, int(w_number))
	#print(wcl)
	return wcl


def vis_heatmap(data_samples, neslist, nes_categories, w_number):
	nesDict = frequency_dict(neslist, nes_categories)
	x_docs, y_words, z_counts  = doHeatmap(nesDict, w_number, data_samples)
	return x_docs, y_words, z_counts


def vis_kmeans(data_samples, num_clusters, pmid_list):
	#use query to get titles
	titles = []
	for pmid in pmid_list:
		temp_titles = db_citation_titles(pmid)
		for t in temp_titles:
			titles.append(t)

	hX, hasher = get_hashing(data_samples)
	clusters = do_kemeans(hX, int(num_clusters)) #list of cluster assignments
	coordinates = do_NMF(hX) #dimensionality reduction for visualization
	#zip coordinates and titles

	zipped_coordinates = zip(coordinates, titles)
	x0_coordinates, y0_coordinates, z0_coordinates, x1_coordinates, y1_coordinates, z1_coordinates, x2_coordinates, y2_coordinates, z2_coordinates, x3_coordinates, y3_coordinates, z3_coordinates, x4_coordinates, y4_coordinates, z4_coordinates, titles0, titles1, titles2, titles3, titles4 = plotKmeans(zipped_coordinates, clusters) #format for Plotly scatterplot


	return x0_coordinates, y0_coordinates, z0_coordinates, x1_coordinates, y1_coordinates, z1_coordinates, x2_coordinates, y2_coordinates, z2_coordinates, x3_coordinates, y3_coordinates, z3_coordinates, x4_coordinates, y4_coordinates, z4_coordinates, titles0, titles1, titles2, titles3, titles4

############ PROCESSING BIODOCS ############################################
#Take pmid_n.txt and get an annotated document, as well as lemmas and named entities
#This method is for user_input NOT already in DB, need to make json, for in DB, no need to make JSON
def do_ALL_multi_preprocessing(user_input):
	logging.info('Beginning multiprocessing for NEW docs')
	t1 = time.time()
	docs = retrieveDocs(user_input)
	multiprocess(docs)
	biodocs = retrieveBioDocs(user_input)
	data_samples, nes_list, total_sentences, sum_tokens = loadBioDoc(biodocs)
	logging.info("Execute everything: done in %0.3fs." % (time.time() - t1))
	return data_samples, nes_list, total_sentences, sum_tokens


#Take annotated docs and return data and nes
#This method is for user_input that IS already in the DB
def do_SOME_multi_preprocessing(user_input):
	logging.info('Beginning multiprocessing for PRE-EXISTING docs')
	t1 = time.time()
	biodocs = retrieveBioDocs(user_input)
	data_samples, nes_list, total_sentences, sum_tokens = loadBioDoc(biodocs)
	logging.info("Execute everything: done in %0.3fs." % (time.time() - t1))
	return data_samples, nes_list, total_sentences, sum_tokens



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




########### WRITING TO JSON / PICKLE ###############################################

def print_lsa(query, user_input, jsonDict):
	#Save the json for @app.route('/reslsa/')
	logging.info('Printing LSA to JSON')
	save_path = '/home/hclent/data/'+str(user_input)+'/' #in the folder of the last pmid
	completeName = os.path.join(save_path, ('lsa_'+(str(query))+'.json')) #with the query for a name
	with open(completeName, 'w') as outfile:
		json.dump(jsonDict, outfile)

def print_lda(query, user_input, jsonLDA):
	#Save the json for @app.route('/reslda/')
	logging.info('Printing LDA to JSON')
	save_path = '/home/hclent/data/'+str(user_input)+'/' #in the folder of the last pmid
	completeName = os.path.join(save_path, ('lda_'+(str(query))+'.json'))  #with the query for a name
	with open(completeName, 'w') as outfile:
		json.dump(jsonLDA, outfile)

def print_data_and_nes(query, user_input, data_samples, nes_list):
	logging.info('Printing data_samples to PICKLE')
	save_path = '/home/hclent/data/'+str(user_input)+'/' #in the folder of the last pmid

	data_completeName = os.path.join(save_path, ('data_samples_'+(str(query))+'.pickle'))  #with the query for a name
	pickle.dump( data_samples, open( data_completeName, "wb" ) )

	logging.info('Printing nes_list to PICKLE')
	nes_completeName = os.path.join(save_path, ('nes_'+(str(query))+'.pickle'))  #with the query for a name
	pickle.dump( nes_list, open( nes_completeName, "wb" ) )


############# GRAVEYARD ##############################################
# def get_data_and_ner(pmid):
# 	biodocs = retrieveBioDocs(str(pmid)) #a bunch of strings
# 	data_samples, neslist = loadBioDoc(biodocs)
# 	return data_samples, neslist