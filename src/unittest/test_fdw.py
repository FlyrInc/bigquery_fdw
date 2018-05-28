import unittest
from collections import OrderedDict

import multicorn
from google.cloud import bigquery

from ..bqclient import BqClient
from ..fdw import ConstantForeignDataWrapper


class Test(unittest.TestCase):

    def setUp(self):
        # Set options
        self.options = {
            'fdw_key': '/opt/key/key.json',
            'fdw_dataset': 'bigquery-public-data.usa_names',
            'fdw_table': 'usa_1910_current',
            'fdw_verbose': False,
            'fdw_sql_dialect': 'standard',
            'fdw_group': 'false',
            'fdw_casting': 'false',
        }

        # Set column list (ordered dict of ColumnDefinition from Multicorn)
        self.columns = OrderedDict([
            ('state', multicorn.ColumnDefinition(
                column_name='state', type_oid=25, base_type_name='text')),
            ('gender', multicorn.ColumnDefinition(
                column_name='gender', type_oid=25, base_type_name='text')),
            ('year', multicorn.ColumnDefinition(
                column_name='year', type_oid=20, base_type_name='bigint')),
            ('name', multicorn.ColumnDefinition(
                column_name='name', type_oid=25, base_type_name='text')),
            ('number', multicorn.ColumnDefinition(
                column_name='number', type_oid=20, base_type_name='bigint'))
        ])

        # Define Quals as defined by Multicorn
        self.quals = [
            multicorn.Qual(field_name='number', operator='>', value=1000),
            multicorn.Qual(field_name='year', operator='=', value=2017),
        ]

        # Set instance of ConstantForeignDataWrapper
        self.fdw = ConstantForeignDataWrapper(self.options, self.columns)

    def test_setOptions(self):
        self.assertIsNone(self.fdw.setOptions(self.options))

    def test_setDatatypes(self):
        self.fdw.setDatatypes()
        self.assertIsInstance(self.fdw.datatypes, list)
        for datatype in self.fdw.datatypes:
            self.assertIsInstance(datatype, tuple)
            self.assertIsInstance(datatype.postgres, str)
            self.assertIsInstance(datatype.bq_standard, str)
            self.assertIsInstance(datatype.bq_legacy, str)

    def test_setConversionRules(self):
        self.fdw.setConversionRules()
        self.assertIsInstance(self.fdw.conversionRules, list)
        for conversionRule in self.fdw.conversionRules:
            self.assertIsInstance(conversionRule, tuple)
            self.assertIsInstance(conversionRule.bq_standard_from, str)
            self.assertIsInstance(conversionRule.bq_standard_to, list)

    def test_setOptionSqlDialect(self):
        self.fdw.setOptionSqlDialect()
        self.assertEqual(self.fdw.dialect, 'standard')

    def test_setOptionSqlDialect_2(self):
        self.fdw.setOptionSqlDialect('legacy')
        self.assertEqual(self.fdw.dialect, 'legacy')

    def test_setOptionSqlDialect_3(self):
        self.fdw.setOptionSqlDialect('non_existent')
        # Should fallback to `standard`
        self.assertEqual(self.fdw.dialect, 'standard')

    def test_setOptionGroupBy(self):
        self.fdw.setOptionGroupBy('true')
        self.assertTrue(self.fdw.groupBy)

    def test_setOptionGroupBy_2(self):
        self.fdw.setOptionGroupBy('false')
        self.assertFalse(self.fdw.groupBy)

    def test_setOptionVerbose(self):
        self.fdw.setOptionVerbose('true')
        self.assertTrue(self.fdw.verbose)

    def test_setOptionVerbose_2(self):
        self.fdw.setOptionVerbose('false')
        self.assertFalse(self.fdw.verbose)

    def test_setOptionCasting(self):
        # Options are a dict casted as a string
        casting = '{"column1": "STRING", "column2": "DATE", "column3": "TIMESTAMP"}'
        self.fdw.setOptionCasting(casting)
        self.assertIsInstance(self.fdw.castingRules, dict)
        for column, cast in self.fdw.castingRules.items():
            self.assertTrue(column in ['column1', 'column2', 'column3'])
            self.assertTrue(cast in ['STRING', 'DATE', 'TIMESTAMP'])

    def test_setOptionCasting_2(self):
        # Nothing should happen if no casting options have been set
        casting = ''
        self.assertIsNone(self.fdw.setOptionCasting(casting))

    def test_getClient(self):
        self.fdw.setClient()
        self.assertIsInstance(self.fdw.getClient(), BqClient)

    def test_setClient(self):
        self.assertIsInstance(self.fdw.setClient(), BqClient)

    def test_execute(self):
        self.fdw.setClient()
        execute = self.fdw.execute(self.quals, self.columns.keys())

        for row in execute:
            # Ensure that the row is an OrderedDict
            self.assertIsInstance(row, OrderedDict)
            # Compare the keys of each row with the expected columns
            self.assertEqual(set(row.keys()), set(
                {'state', 'gender', 'year', 'name', 'number'}))

    def test_buildQuery(self):
        self.fdw.bq = self.fdw.getClient()
        query, parameters = self.fdw.buildQuery(self.quals, self.columns)

        self.assertIsInstance(query, str)
        self.assertIsInstance(parameters, list)
        for parameter in parameters:
            self.assertIsInstance(
                parameter, bigquery.query.ScalarQueryParameter)

    def test_buildQuery_2(self):
        # Test with grouping option
        self.fdw.groupBy = True

        self.fdw.bq = self.fdw.getClient()
        query, parameters = self.fdw.buildQuery(self.quals, self.columns)

        self.assertIsInstance(query, str)
        self.assertIsInstance(parameters, list)
        for parameter in parameters:
            self.assertIsInstance(
                parameter, bigquery.query.ScalarQueryParameter)

    def test_buildColumnList(self):
        self.assertEqual(self.fdw.buildColumnList(
            self.columns), 'state  as state, gender  as gender, year  as year, name  as name, number  as number')

    def test_buildColumnList_2(self):
        self.assertEqual(self.fdw.buildColumnList(
            self.columns, 'GROUP_BY'), 'state , gender , year , name , number')

    def test_buildColumnList_3(self):
        # Test with counting pseudo column
        c = self.columns
        c['_fdw_count'] = multicorn.ColumnDefinition(
            column_name='_fdw_count', type_oid=20, base_type_name='bigint')

        self.assertEqual(self.fdw.buildColumnList(
            c), 'state  as state, gender  as gender, year  as year, name  as name, number  as number, count(*)  as _fdw_count')

    def test_buildColumnList_4(self):
        # Test with counting pseudo column
        c = self.columns
        c['_fdw_count'] = multicorn.ColumnDefinition(
            column_name='_fdw_count', type_oid=20, base_type_name='bigint')

        self.assertEqual(self.fdw.buildColumnList(
            c, 'GROUP_BY'), 'state , gender , year , name , number')

    def test_buildColumnList_5(self):
        # Test with partition pseudo column
        c = self.columns
        c['partition_date'] = multicorn.ColumnDefinition(
            column_name='partition_date', type_oid=0, base_type_name='date')

        self.assertEqual(self.fdw.buildColumnList(
            c), 'state  as state, gender  as gender, year  as year, name  as name, number  as number, _PARTITIONTIME  as partition_date')

    def test_buildColumnList_6(self):
        # Test with partition pseudo column
        c = self.columns
        c['partition_date'] = multicorn.ColumnDefinition(
            column_name='partition_date', type_oid=0, base_type_name='date')

        self.assertEqual(self.fdw.buildColumnList(
            c, 'GROUP_BY'), 'state , gender , year , name , number , _PARTITIONTIME')

    def test_buildColumnList_7(self):
        # Test `SELECT *`
        self.assertEqual(self.fdw.buildColumnList(None), '*')

    def test_buildColumnList_8(self):
        # Test no columns when grouping by
        self.assertEqual(self.fdw.buildColumnList(None, 'GROUP_BY'), '')

    def test_setTimeZone(self):
        self.fdw.convertToTz = 'US/Eastern'
        self.assertEqual(self.fdw.setTimeZone(
            'column1', 'DATE').strip(), 'DATE(column1, "US/Eastern")')

    def test_setTimeZone_2(self):
        self.fdw.convertToTz = 'US/Eastern'
        self.assertEqual(self.fdw.setTimeZone(
            'column1', 'DATETIME').strip(), 'DATETIME(column1, "US/Eastern")')

    def test_setTimeZone_3(self):
        self.fdw.convertToTz = None
        self.assertEqual(self.fdw.setTimeZone(
            'column1', 'DATE').strip(), 'column1')

    def test_setTimeZone_4(self):
        self.fdw.convertToTz = None
        self.assertEqual(self.fdw.setTimeZone(
            'column1', 'DATETIME').strip(), 'column1')

    def test_castColumn(self):
        # Options are a dict casted as a string
        casting = '{"number": "STRING"}'
        self.fdw.setOptionCasting(casting)

        self.assertEqual(self.fdw.castColumn(
            'number', 'number', 'INT64'), 'CAST(number as STRING)')

    def test_castColumn_2(self):
        # Options are a dict casted as a string
        casting = '{"number": "STRING"}'
        self.fdw.setOptionCasting(casting)

        # Casting should fail on columns not in the casting rules
        self.assertEqual(self.fdw.castColumn(
            'year', 'year', 'INT64'), 'year')

    def test_addColumnAlias(self):
        self.assertEqual(self.fdw.addColumnAlias(
            'some_column'), ' as some_column')

    def test_addColumnAlias_2(self):
        self.assertEqual(self.fdw.addColumnAlias(
            'some_column', False), '')

    def test_buildWhereClause(self):
        self.fdw.bq = self.fdw.getClient()
        clause, parameters = self.fdw.buildWhereClause(self.quals)

        self.assertIsInstance(clause, str)
        self.assertIsInstance(parameters, list)
        for parameter in parameters:
            self.assertIsInstance(
                parameter, bigquery.query.ScalarQueryParameter)

    def test_getOperator(self):
        self.assertEqual(self.fdw.getOperator('='), '=')

    def test_getOperator_2(self):
        self.assertEqual(self.fdw.getOperator('~~'), 'LIKE')

    def test_getOperator_3(self):
        self.assertEqual(self.fdw.getOperator('!~~'), 'NOT LIKE')

    def test_getBigQueryDatatype(self):
        self.assertEqual(self.fdw.getBigQueryDatatype('number'), 'INT64')

    def test_getBigQueryDatatype_2(self):
        self.assertEqual(self.fdw.getBigQueryDatatype(
            'number', 'legacy'), 'INTEGER')

    def test_setParameter(self):
        self.fdw.bq = self.fdw.getClient()
        self.assertIsInstance(self.fdw.setParameter(
            'column', 'STRING', 'some string'), bigquery.query.ScalarQueryParameter)
