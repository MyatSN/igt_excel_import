{
    'name': 'Excel Import',
    'version': '14.0.1.1.0',
    'category': 'Tools',
    'summary': 'Import lines from Excel into models (wizard + configs)',
    'description': """
      <p>This module allows importing Excel files into Odoo.</p>
      <ul>
      <li>Import line items from Excel</li> 
      </ul>
     """,
    'author': 'IGT',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/igt_excel_import_views.xml',
        'wizards/igt_excel_import_wizard.xml'
    ],
    'images': ['static/description/icon.png','static/description/cover.png'],
    'external_dependencies': {'python': ['openpyxl']},
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'website': 'https://github.com/MyatSN/igt_excel_import',
}