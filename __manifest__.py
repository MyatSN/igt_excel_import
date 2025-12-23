{
    'name': 'Excel Import',
    'version': '14.0.1.1.0',
    'category': 'Tools',
    'summary': 'Import lines from Excel into models (wizard + configs)',
    'author': 'IGT',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/igt_excel_import_views.xml',
        'wizards/igt_excel_import_wizard.xml'
    ],
    'external_dependencies': {'python': ['openpyxl']},
    'installable': True,
    'application': False,
}