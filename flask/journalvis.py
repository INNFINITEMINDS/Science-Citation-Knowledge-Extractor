import re
from collections import defaultdict


def journals_vis(journals, dates):
	years_list = []
	print(dates) #step1 : get years
	for d in dates:
		y = re.sub('.[A-Z]{1}[a-z]{2}(.?\d{1,2})?', '', d) #delete month and day
		y = re.sub('\D', '', y) #delete any extra letters that escaped for some reason
		years_list.append(y)
	#print(years_list)

	years_range = (years_list[-1], years_list[0]) #define years range with (oldest, newest)
	#print(years_range)

	#Associate journals with years
	journal_year = list(zip(journals, years_list)) #('Scientific Reports', '2016')
	#print(journal_year)

	#Dictionary with "Journal": [year, year]
	#For looking up the years
	jyDict = defaultdict(list)
	i = 0
	for j in journals:
		if j == (journal_year[i][0]):
			jyDict[j] += [journal_year[i][1]]
			i+=1
	#print(jyDict)

	#Dictionary with "Journal": Number-of-publications
	#For looking up the total
	journalsTotalDict = defaultdict(lambda: 0)
	sum = 0
	for j in journals:
		journalsTotalDict[j] += 1
		sum +=1
	#print(journalsTotalDict)
	unique_journals = list(journalsTotalDict.keys())
	#print(unique_journals)

	publication_data = []
	for j in unique_journals:
		#print(j)
		#Initiate the dictionary for this journal
		journal_data = {
			"name": j,
			"articles": [], #[[year, number], [year, number]]
			"total": journalsTotalDict[j]   #total can get from journalsTotalDict with key (total is value)
		}
		#print("Years a paper was in this journal: "+ str(jyDict[j]))
		for year in range(int(years_range[0]), int(years_range[1]) + 1):
			#print("checking " +str(year) +" ...")
			sum = 0
			for entry in jyDict[j]:
				#print(" ... against "+str(entry))
				if year == int(entry):
					#print("The years match so I'm going to count now")
					sum+=1
				year_sum = [year, sum]
				#print(year_sum)
			journal_data["articles"].append(year_sum)

		publication_data.append(journal_data)

	#Get some info about the publication before changing it to a string for the json
	some_journal = publication_data[0]
	print(some_journal)
	start_date = some_journal['articles'][0][0]
	end_date = some_journal['articles'][-1][0]
	year_range = (start_date, end_date)
	print(year_range)
	publication_data = re.sub('\'', '\"', str(publication_data)) #json needs double quotes, not single quotes
	return (publication_data)