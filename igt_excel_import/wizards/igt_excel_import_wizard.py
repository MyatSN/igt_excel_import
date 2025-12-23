import base64
import io
import ast
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, MissingError

try:
    import openpyxl  # type: ignore - optional dependency
    _HAS_OPENPYXL = True
except Exception:
    openpyxl = None
    _HAS_OPENPYXL = False


class IGTExcelImportWizard(models.TransientModel):
    _name = 'igt.excel.import.wizard'
    _description = 'IGT Excel Import (wizard)'

    config_id = fields.Many2one('igt.excel.import', string='Config')
    working_id = fields.Integer(string='Active ID')
    file = fields.Binary(string='Import File')
    filename = fields.Char(string='Filename')
    @api.model
    def default_get(self, default_fields):
        res = super(IGTExcelImportWizard, self).default_get(default_fields)
        server_action_id = self._context.get('default_server_action_id') or self._context.get('server_action_id')
        active_id = self._context.get('active_id')
        if active_id:
            res.update({'working_id': active_id})
        if server_action_id:
            config_id = self.env['igt.excel.import'].search([('server_action_id','=', server_action_id)])
            if not config_id:
                raise MissingError('Configuration not found. Please contact your administrator.')
            res.update({'config_id': config_id.id})
        return res

    def action_get_excel(self):
        """Return an action that triggers download of the selected config's sample file."""
        self.ensure_one()
        config = self.config_id
        if not config or not config.sample_file:
            raise UserError(_('No sample file defined on the selected configuration.'))
        filename = config.sample_filename or (config.name + '.xlsx')
        try:
            from urllib.parse import quote
        except Exception:
            from urllib import quote
        url = '/web/content/igt.excel.import/%s/sample_file/%s?download=true' % (config.id, quote(filename))
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    def action_import(self):
        if not self.config_id:
            raise UserError(_('Please select an Import Configuration.'))
        if not _HAS_OPENPYXL:
            raise UserError(_('openpyxl is required to import xlsx files. Please install it in your environment.'))
        if not self.file:
            raise UserError(_('Please upload an Excel file to import.'))

        # resolve parameters from the chosen config
        parent_model = self.config_id.model_id.model
        import_field = self.config_id.import_field_id
        if not import_field:
            raise UserError(_('The chosen config does not specify an import (one2many) field.'))
        line_model = import_field.relation

        # determine active_id (the parent record id)
        active_id = self.working_id or self.env.context.get('active_id')
        if not active_id:
            raise UserError(_('This wizard must be opened from a record (via Import lines button on the form).'))

        parent_name = self.config_id.parent_field_id.name if self.config_id.parent_field_id else None
        if not parent_name:
            parent_field = self.env['ir.model.fields'].search([
                ('model', '=', line_model), ('relation', '=', parent_model), ('ttype', '=', 'many2one')
            ], limit=1)
            parent_name = parent_field.name if parent_field else None
            if not parent_name:
                raise UserError(_('Cannot find a many2one field on %s linking to %s; please update the import configuration') % (line_model, parent_model))

        data = base64.b64decode(self.file)
        wb = openpyxl.load_workbook(filename=io.BytesIO(data), read_only=True)
        ws = wb.active
        rows = list(ws.rows)
        if not rows:
            raise UserError(_('Uploaded file is empty'))
        header = [str(cell.value).strip() if cell.value is not None else '' for cell in rows[0]]
        created = 0
        for row in rows[1:]:
            vals = {parent_name: active_id}
            for idx, cell in enumerate(row):
                if idx >= len(header):
                    continue
                col = header[idx]
                if not col:
                    continue
                else:
                    colmap =self.config_id.line_ids.filtered(lambda l: l.column_name == col) or False
                    if not colmap:
                        continue
                    key = colmap[0].field_id.name
                    key_domain = colmap[0].domain and ast.literal_eval(colmap[0].domain) or []
                value = cell.value
                fmeta = self.env['ir.model.fields'].search([('model', '=', line_model), ('name', '=', key)], limit=1)
                if not fmeta:
                    continue
                if fmeta.ttype == 'many2one':
                    if value is None:
                        vals[key] = False
                    elif isinstance(value, (int, float)) and float(value).is_integer():
                        vals[key] = int(value)
                    else:
                        comodel = self.env[fmeta.relation]
                        res = comodel.search([('name', '=', str(value))] + key_domain, limit=1)
                        if not res:
                            raise UserError(_('Could not find a record with name "%s" for column "%s".') % (value, col))
                        vals[key] = res.id
                elif fmeta.ttype in ('integer', 'float'):
                    vals[key] = 0 if value is None else value
                elif fmeta.ttype == 'date':
                    vals[key] = value.date() if isinstance(value, datetime) else value
                else:
                    vals[key] = value
            try:
                self.env[line_model].create(vals)
                created += 1
            except Exception as e:
                raise UserError(_('Error creating line: %s') % e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import finished'),
                'message': _('%s lines created') % created,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
