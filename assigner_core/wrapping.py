def get_UMI_counting(in_df, options):
	import numpy as np
	import math

#	log10_res = 3
	log10_res = math.ceil(-math.log10(options.smooth_res))
#	smooth_res = 10 ** (-log10_res)

	print("Generating UMI counting table ...", flush = True)
	df = in_df.loc[in_df['BC'].str.len() == options.BC_len, ['BC', 'UMI']].groupby('BC').nunique().sort_values(by = 'UMI', ascending = False).reset_index()
	df['idx'] = df.index.values + 1

	print("Calculating log10(slope) ...", flush = True)
	df['log10_idx'] = np.log10(df['idx'])
	df['log10_UMI'] = np.log10(df['UMI'])

	df['r_log10_idx'] = np.log10(df['idx']).round(decimals = log10_res)
#	df['r_log10_UMI'] = np.log10(df['UMI']).round(decimals = 4)
	df['r_log10_UMI'] = np.log10(df['UMI']).round(decimals = (log10_res + 1))

	log10_idx_array = np.asarray(df.loc[:, ["log10_idx"]])
	log10_UMI_array = np.asarray(df.loc[:, ["log10_UMI"]])

	df['log10_slope'] = np.append(np.nan, \
                            (log10_UMI_array[0:log10_UMI_array.shape[0] - 1, 0] -     \
                             log10_UMI_array[1:log10_UMI_array.shape[0],     0]) /    \
                            (log10_idx_array[0:log10_idx_array.shape[0] - 1, 0] -     \
                             log10_idx_array[1:log10_idx_array.shape[0],     0]) * -1)

	print("Computing median log10(slope) ...", flush = True)
	for i in np.arange(min(df['r_log10_idx']), max(df['r_log10_idx']), options.smooth_res):
		idx = round(i, log10_res)
		in_arr = np.asarray(df.loc[df['r_log10_idx'] == idx, ['log10_slope']])
		med_val = 0
		if in_arr.shape[0] > 0:
			med_val = float(np.median(in_arr))
			res_arr = np.repeat(med_val, in_arr.shape[0])
			df.loc[df['r_log10_idx'] == idx, ['med_log10_slope']] = res_arr
	print()

	return df

def estimate_cell_no(df, options):
	import numpy as np

	#=== min_cell_no (1 based, so need to minus 1 during iloc) ===
	df = df.iloc[(options.min_cellno - 1):]

	log10_idx_ori = np.max(df.loc[df['med_log10_slope'] == np.nanmax(df['med_log10_slope']), "log10_idx"])

	#===including 10% more CB===
	log10_idx     = np.max(df.loc[df['med_log10_slope'] == np.nanmax(df['med_log10_slope']), "log10_idx"]) * (1 + float(options.CB_no_ext))

	return np.max(df.loc[df['log10_idx'] <= log10_idx_ori, "idx"]), \
               np.max(df.loc[df['log10_idx'] <= log10_idx,     "idx"])

def estimate_rescue_cell_no(df):
	print("\nestimate_rescue_cell_no:")
	print(df)
	est_rescue_CB_no = 10
	return est_rescue_CB_no

def batch_seq_comp(query, target, options):
	import time, distance, os

	print("Calculating Levenshtein distance on " + str(query[0]) + ": " + query[1] + " ...")
	start_time = time.time()

# target:
#          idx                BC
# 0          1  CTACGAAGTGATGAGG
# 1          2  TTGTGCCTCATTGACA

	target = target.loc[target["idx"] > query[0], :].copy()

	target.loc[:, "id1"]      = query[0]
	target.loc[:, "BC1"]      = query[1]
	target.loc[:, "distance"] = target.apply(lambda x: distance.levenshtein(x["BC"], x["BC1"]), axis = 1)

	tmp_f = os.path.join(options.tmp_dir, "assigner_tmp_") + str(query[0]) + ".tsv"

	target.loc[target["distance"] <= options.CB_mrg_thr, ["id1", "idx", "distance"]].to_csv(tmp_f, header = None, index = None, sep = "\t")

	time_elapse = time.time() - start_time
	hours   = time_elapse // 3600
	rest_t  = time_elapse % 3600
	minutes = rest_t // 60
	seconds = rest_t % 60
	print("Calc. LD on " + query[1] + " spent %d : %d : %.2f" % (hours, minutes, seconds))

	return 1

def seq_comp(batch_data, options):
	import distance

	return [batch_data['id1'], batch_data['id2'], distance.levenshtein(batch_data['BC1'], batch_data['BC2'])]

def merge_cb_new(mrg_sel, options):
	import pandas as pd
	import os

	with open(options.CB_mrg_dist_ff, "wt") as fh:
		fh.write("id1\tid2\tdistance\n")

	cmd = 'cat ' + os.path.join(options.tmp_dir, 'assigner_tmp_*.tsv >> ') + options.CB_mrg_dist_ff
	os.system(cmd)

	cmd = 'rm '  + os.path.join(options.tmp_dir, 'assigner_tmp_*.tsv')
	os.system(cmd)

	if options.CB_mrg_dist_compression:
		cmd = 'gzip -f ' + options.CB_mrg_dist_ff
		os.system(cmd)

	dist_df = pd.read_csv(options.CB_mrg_dist, sep = "\t", header = 0, compression = options.CB_mrg_dist_compression)

	res = dict()
	for idx in mrg_sel['idx']:
		res[str(idx)] = str(idx)

	for idx, row in dist_df.iterrows():
		res[str(row['id2'])] = res[str(row['id1'])]

	return pd.DataFrame.from_dict(res, orient = 'index').reset_index().rename(columns = {'index': 'id1', 0: 'id2'})

def merge_cb(mrg_sel, dist_df, mrg_dist):
	import pandas as pd

	res = dict()

	for idx in mrg_sel['idx']:
		res[str(idx)] = str(idx)

	for idx, row in dist_df.iterrows():
		if row['distance'] <= int(mrg_dist):
			res[str(row['id2'])] = res[str(row['id1'])]

	res_df = pd.DataFrame.from_dict(res, orient = 'index').reset_index().rename(columns = {'index': 'id1', 0: 'id2'})

	return res_df

