"""Regression tests for metric definitions and misleading edge cases.

Run with Python's standard library runner: python -m unittest discover -s tests -v
No test writes project outputs or requires network access.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODULES = {}


def module(slug):
    if slug not in MODULES:
        path = ROOT / 'projects' / slug / 'scripts' / 'analyze.py'
        spec = importlib.util.spec_from_file_location(slug.replace('-', '_'), path)
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        MODULES[slug] = loaded
    return MODULES[slug]


class SalesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = module('ecommerce-sales-analysis')

    def test_sample_totals_and_category_order(self):
        result = self.analysis.analyze(self.analysis.load_data())
        overview = result['overview'].iloc[0]
        self.assertEqual(overview['order_count'], 50)
        self.assertAlmostEqual(overview['revenue'], 80860)
        self.assertAlmostEqual(overview['average_order_value'], 1617.2)
        self.assertEqual(len(result['monthly_sales']), 12)
        self.assertEqual(result['category_sales']['product_category'].tolist(), ['Electronics', 'Home', 'Fashion'])
        self.assertAlmostEqual(result['monthly_sales']['revenue'].sum(), overview['revenue'])

    def test_analysis_does_not_mutate_input(self):
        data = self.analysis.load_data()
        before = data.copy(deep=True)
        self.analysis.analyze(data)
        pd.testing.assert_frame_equal(data, before)

    def test_duplicate_order_is_rejected(self):
        data = self.analysis.load_data()
        with self.assertRaises(ValueError):
            self.analysis.analyze(pd.concat([data, data.iloc[[0]]], ignore_index=True))

    def test_negative_price_is_rejected(self):
        data = self.analysis.load_data()
        data.loc[0, 'unit_price'] = -1
        with self.assertRaises(ValueError):
            self.analysis.analyze(data)

    def test_zero_revenue_share_is_undefined(self):
        data = self.analysis.load_data()
        data['unit_price'] = 0
        result = self.analysis.analyze(data)
        self.assertEqual(result['overview'].iloc[0]['revenue'], 0)
        self.assertTrue(result['category_sales']['revenue_share_pct'].isna().all())


class BehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = module('user-behavior-analysis')

    def events(self, names, times=None, sessions=None):
        count = len(names)
        return pd.DataFrame({
            'user_id': ['U1'] * count, 'event_type': names,
            'event_time': times if times is not None else pd.date_range('2024-01-01', periods=count, freq='min'),
            'device': ['Mobile'] * count, 'region': ['East'] * count,
            'session_id': sessions if sessions is not None else ['S1'] * count,
        })

    def test_sample_ordered_session_funnel(self):
        result = self.analysis.analyze(self.analysis.load_data())
        funnel = result['funnel_analysis']
        self.assertEqual(funnel['sessions'].tolist(), [10, 9, 7, 5])
        self.assertAlmostEqual(funnel.iloc[-1]['entry_conversion_pct'], 50)
        self.assertEqual(result['overview'].iloc[0]['input_event_rows'], 35)

    def test_duplicate_events_do_not_inflate_funnel(self):
        data = self.analysis.load_data()
        duplicated = pd.concat([data, data.iloc[[0]], data.iloc[[0]]], ignore_index=True)
        result = self.analysis.analyze(duplicated)
        self.assertEqual(result['funnel_analysis']['sessions'].tolist(), [10, 9, 7, 5])
        self.assertEqual(result['overview'].iloc[0]['exact_duplicates_removed'], 2)

    def test_out_of_order_events_do_not_complete_funnel(self):
        data = self.events(['page_view', 'checkout', 'add_to_cart', 'purchase'])
        result = self.analysis.analyze(data)
        self.assertEqual(result['funnel_analysis']['sessions'].tolist(), [1, 1, 0, 0])

    def test_equal_timestamps_do_not_prove_order(self):
        data = self.events(['page_view', 'add_to_cart', 'checkout', 'purchase'], times=['2024-01-01'] * 4)
        self.assertEqual(self.analysis.analyze(data)['funnel_analysis']['sessions'].tolist(), [1, 0, 0, 0])

    def test_stages_in_different_sessions_are_not_joined(self):
        data = self.events(['page_view', 'add_to_cart', 'checkout', 'purchase'], sessions=['S1', 'S2', 'S2', 'S2'])
        self.assertEqual(self.analysis.analyze(data)['funnel_analysis']['sessions'].tolist(), [1, 0, 0, 0])

    def test_duration_longer_than_a_day_uses_total_seconds(self):
        data = self.events(['page_view', 'add_to_cart'], times=['2024-01-01 00:00:00', '2024-01-03 01:00:00'])
        self.assertEqual(self.analysis.analyze(data)['session_activity'].iloc[0]['duration_minutes'], 49 * 60)

    def test_empty_funnel_has_no_infinite_conversion(self):
        data = self.events(['page_view']).iloc[:0]
        funnel = self.analysis.analyze(data)['funnel_analysis']
        self.assertEqual(funnel['sessions'].tolist(), [0, 0, 0, 0])
        self.assertTrue(funnel['step_conversion_pct'].isna().all())


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = module('marketing-campaign-evaluation')

    def test_sample_channel_metrics(self):
        result = self.analysis.analyze(self.analysis.load_data())
        email = result['channel_performance'].set_index('channel').loc['Email']
        self.assertAlmostEqual(email['ctr_pct'], 2950 / 30000 * 100)
        self.assertAlmostEqual(email['cpa'], 19.2)
        self.assertAlmostEqual(email['roas'], 14500 / 2400)
        self.assertNotIn('roi', email.index)
        comparison = result['variant_comparison']
        self.assertEqual(len(comparison), 15)
        self.assertTrue(comparison['comparable_group'].all())

    def test_aggregate_ratios_are_not_unweighted_means(self):
        data = pd.DataFrame({
            'channel': ['X', 'X'], 'impressions': [100, 1000], 'clicks': [20, 10],
            'spend': [10, 100], 'revenue': [20, 150], 'conversions': [2, 1],
        })
        grouped = self.analysis.aggregate_metrics(data, ('channel',)).iloc[0]
        self.assertAlmostEqual(grouped['ctr_pct'], 30 / 1100 * 100)
        self.assertNotAlmostEqual(grouped['ctr_pct'], (20 + 1) / 2)

    def test_zero_denominators_produce_nan_not_infinity(self):
        data = self.analysis.load_data().iloc[[0]].copy()
        data[list(self.analysis.AMOUNT_COLUMNS)] = 0
        metrics = self.analysis.analyze(data)['campaign_metrics'].iloc[0]
        for column in ['ctr_pct', 'cvr_pct', 'cpc', 'cpm', 'cpa', 'roas', 'ad_spend_return_proxy_pct']:
            self.assertTrue(pd.isna(metrics[column]), column)

    def test_no_control_means_no_control_comparison(self):
        data = self.analysis.load_data()
        data = data.loc[data['variant'].ne('Control')]
        comparison = self.analysis.compare_variants(data)
        self.assertFalse(comparison['comparable_group'].any())
        self.assertTrue(comparison['cvr_delta_pp_vs_control'].isna().all())


class SegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = module('customer-segmentation')

    def test_tied_values_have_equal_scores(self):
        values = pd.Series([1] * 12 + [2] * 4 + [3, 4, 5, 6])
        scores = self.analysis.quantile_score(values)
        self.assertTrue(scores.between(1, 5).all())
        self.assertTrue(pd.DataFrame({'value': values, 'score': scores}).groupby('value')['score'].nunique().eq(1).all())

    def test_constant_scores_are_neutral(self):
        scores = self.analysis.quantile_score(pd.Series([7] * 20))
        self.assertEqual(scores.unique().tolist(), [3])

    def test_recency_scores_reverse_direction(self):
        values = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        high = self.analysis.quantile_score(values)
        low = self.analysis.quantile_score(values, higher_is_better=False)
        pd.testing.assert_series_equal(low, 6 - high)
        self.assertGreater(low.iloc[0], low.iloc[-1])

    def test_sample_profiles_preserve_customer_and_amount_totals(self):
        data = self.analysis.load_data()
        result = self.analysis.analyze(data)
        self.assertEqual(result['rfm_segments']['count'].sum(), 20)
        self.assertEqual(result['kmeans_clusters']['count'].sum(), 20)
        self.assertAlmostEqual(result['rfm_segments']['total_monetary'].sum(), data['monetary'].sum())
        self.assertEqual(result['customer_segments']['cluster'].nunique(), 4)

    def test_too_many_clusters_are_rejected(self):
        data = self.analysis.load_data().iloc[[0]]
        with self.assertRaises(ValueError):
            self.analysis.cluster_customers(data, n_clusters=4)


class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = module('product-recommendation-analysis')

    def test_sample_rule_has_recomputed_support_confidence_and_lift(self):
        result = self.analysis.analyze(self.analysis.load_data())
        rules = result['association_rules']
        matching = rules.loc[
            rules['antecedents'].map(lambda value: tuple(value) == ('Smartphone',))
            & rules['consequents'].map(lambda value: tuple(value) == ('Phone Case',))
        ]
        self.assertEqual(len(matching), 1)
        rule = matching.iloc[0]
        self.assertAlmostEqual(rule['support'], 5 / 15)
        self.assertAlmostEqual(rule['confidence'], 1)
        self.assertAlmostEqual(rule['lift'], 15 / 7)

    def test_support_denominator_is_local_and_duplicates_count_once(self):
        baskets = [['A', 'B'], ['A'], ['A', 'A']]
        itemsets = self.analysis.get_frequent_itemsets(baskets, min_support=0.1)
        support = dict(zip(itemsets['itemset'], itemsets['support']))
        self.assertEqual(support[('A',)], 1)
        self.assertAlmostEqual(support[('B',)], 1 / 3)
        self.analysis.get_frequent_itemsets([['X']] * 10)
        repeated = self.analysis.get_frequent_itemsets(baskets, min_support=0.1)
        pd.testing.assert_frame_equal(itemsets, repeated)

    def test_empty_itemsets_have_stable_schema(self):
        empty = self.analysis.get_frequent_itemsets([])
        self.assertTrue(empty.empty)
        self.assertEqual(empty.columns.tolist(), list(self.analysis.ITEMSET_COLUMNS))

    def test_no_joint_baskets_gives_empty_rules_without_keyerror(self):
        baskets = [['A'], ['B']]
        itemsets = self.analysis.get_frequent_itemsets(baskets)
        rules = self.analysis.get_association_rules(itemsets, baskets)
        self.assertTrue(rules.empty)
        self.assertEqual(rules.columns.tolist(), list(self.analysis.RULE_COLUMNS))
        self.assertTrue(rules.nlargest(5, 'lift').empty)

    def test_self_is_removed_before_ranking_tied_similarities(self):
        similarity = pd.DataFrame(np.ones((4, 4)), index=list('abcd'), columns=list('abcd'))
        top = self.analysis.get_similar_items(similarity, 'd', top_n=2)
        self.assertEqual(top['product_name'].tolist(), ['a', 'b'])

    def test_sequence_serialization_is_sorted_json(self):
        table = pd.DataFrame({'itemset': [frozenset(['B', 'A'])]})
        result = self.analysis.serialize_sequences(table, ('itemset',))
        self.assertEqual(result.loc[0, 'itemset'], '["A","B"]')
        self.assertIsInstance(table.loc[0, 'itemset'], frozenset)

    def test_empty_analysis_still_has_renderable_dashboard(self):
        data = self.analysis.load_data().iloc[:0]
        result = self.analysis.analyze(data)
        self.assertTrue(result['association_rules'].empty)
        figure = self.analysis.plot_dashboard(result)
        try:
            figure.canvas.draw()
            self.assertEqual(len(figure.axes), 4)
        finally:
            self.analysis.plt.close(figure)

    def test_analysis_does_not_mutate_input(self):
        data = self.analysis.load_data()
        before = data.copy(deep=True)
        self.analysis.analyze(data)
        pd.testing.assert_frame_equal(data, before)


if __name__ == '__main__':
    unittest.main()
