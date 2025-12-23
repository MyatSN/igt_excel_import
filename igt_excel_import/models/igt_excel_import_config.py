from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IGTExcelImport(models.Model):
    _name = 'igt.excel.import'
    _description = 'IGT Excel Import Configuration'

    name = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', string='Document Model', required=True,
                               help='Parent document model', ondelete='cascade')
    model_name = fields.Char(related='model_id.model')
    child_model_id = fields.Many2one('ir.model', string='Import Model', required=True,
                                     help='Model used to create lines', ondelete='cascade')
    child_model_name = fields.Char(related='child_model_id.model')
    import_field_id = fields.Many2one('ir.model.fields', string='Import fields',
                                      domain="[('ttype','=', 'one2many'),('model', '=', model_name)]",
                                      help='One2many field on the parent model that will receive lines')
    parent_field_id = fields.Many2one('ir.model.fields', string='Parent field',
                                      domain="[ ('ttype','=', 'many2one'),('model', '=', child_model_name)]")

    sample_file = fields.Binary(string='Sample file')
    sample_filename = fields.Char(string='Sample filename')

    line_ids = fields.One2many('igt.excel.import.line', 'config_id', string='Column setup')

    # Publish state to control whether an import action is available on the parent model
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published')], default='draft')
    server_action_id = fields.Many2one('ir.actions.server', string='Server Action', ondelete='cascade')

    @api.constrains('import_field_id', 'parent_field_id')
    def _check_fields(self):
        for rec in self:
            if rec.import_field_id and rec.import_field_id.model != rec.model_id.model:
                raise UserError(_('Import field must be a one2many defined on the parent model'))
            if rec.parent_field_id and rec.parent_field_id.model != rec.child_model_id.model:
                raise UserError(_('Parent field must be a many2one on the child model'))

    def action_publish(self):
        """Publish the config: create a server action bound to the parent model.

        The server action will open the existing import wizard and pass this
        config id via context (default_config_id).
        """
        for rec in self:
            if rec.state == 'published':
                continue
            if not rec.model_id:
                raise UserError(_('Please set the target Document Model before publishing.'))
            if not rec.import_field_id:
                raise UserError(_('Please set the Import field (one2many on parent model) before publishing.'))
            # Find an existing shared server action for this parent model
            action_name = self.name
            existing = self.env['ir.actions.server'].search([
                ('name', '=', action_name), ('binding_model_id', '=', rec.model_id.id)
            ], limit=1)
            if existing:
                # reuse existing shared action
                rec.server_action_id = existing
            else:
                # create shared server action bound to the parent model that opens the wizard
                # The action will not preselect a config; the wizard will present a dropdown.
                # We create the record first, then write the code containing the server_action id
                server_action = self.env['ir.actions.server'].create({
                    'name': action_name,
                    'model_id': rec.model_id.id,
                    'binding_model_id': rec.model_id.id,
                    'binding_view_types': 'form',
                    'state': 'code',
                    'code': '',
                })
                code = (
                    "action = env.ref('igt_excel_import.action_open_excel_import_wizard').read()[0]\n" 
                    "action['context'] = {'active_id': records.id, 'active_model': records._name, 'server_action_id': %s}\n"
                ) % (server_action.id)
                server_action.write({'code': code})
                rec.server_action_id = server_action
            rec.state = 'published'

    def action_unpublish(self):
        """Unpublish the config: remove the bound server action only if no other
        published configs reference it."""
        for rec in self:
            action = rec.server_action_id
            if action:
                # detach this config from the action
                rec.server_action_id = False
                # check if any other published config references the same action
                others = self.search([('server_action_id', '=', action.id)])
                if not others:
                    try:
                        action.unlink()
                    except Exception:
                        raise UserError(_('Could not remove server action for %s') % rec.name)
            rec.state = 'draft'

    def unlink(self):
        # ensure server action is removed if no published configs remain
        actions_to_check = set(self.mapped('server_action_id.id')) - {False}
        res = super(IGTExcelImport, self).unlink()
        for aid in actions_to_check:
            if not self.search([('server_action_id', '=', aid)]):
                try:
                    self.env['ir.actions.server'].browse(aid).unlink()
                except Exception:
                    pass
        return res


class IGTExcelImportLine(models.Model):
    _name = 'igt.excel.import.line'
    _description = 'IGT Excel Import Column'

    config_id = fields.Many2one('igt.excel.import', string='Config', ondelete='cascade', required=True)
    model_name = fields.Char(related='config_id.child_model_name')
    column_name = fields.Char(string='Column name', required=True)
    field_id = fields.Many2one('ir.model.fields', string='Field', ondelete='cascade',
                               domain="[('model','=', model_name)]",
                               help='Target field on child model')
    domain = fields.Char(string='Domain', help='Optional domain to apply when resolving many2one values')

    def related_child_model(self):
        # fallback domain helper for xml; used only for UI; not used in python directly
        return self.config_id.child_model_id.model if self.config_id and self.config_id.child_model_id else False
